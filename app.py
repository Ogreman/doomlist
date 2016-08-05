import os
import json
import datetime
import requests
import flask
import slacker
import csv
import StringIO

from scrapers import scrapers
from delayed import delayed
from models import models

from flask.ext.cacheify import init_cacheify


app = flask.Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.cache = init_cacheify(app)

URL_REGEX = "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
SCRAPE_TRIGGER_WORD = "scrape"
ALBUM_TEMPLATE = "{name} by {artist}: {url}"
BANDCAMP_URL_TEMPLATE = "https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/artwork=small"
API_TOKEN = app.config['API_TOKEN']
BOT_URL_TEMPLATE = app.config['BOT_URL_TEMPLATE']
DEFAULT_CHANNEL = app.config['DEFAULT_CHANNEL']
DOOM_BOT_URL = BOT_URL_TEMPLATE.format(channel=DEFAULT_CHANNEL)
APP_TOKENS = [
    token for key, token in os.environ.items()
    if key.startswith('APP_TOKEN')
]


@delayed.queue_func
def deferred_scrape(scrape_function, callback, response_url=DOOM_BOT_URL):
    try:
        slack = slacker.Slacker(API_TOKEN)
        requests.post(response_url, data=json.dumps({'text': 'Getting channel history...'}))
        response = slack.channels.history(os.environ['SLACK_CHANNEL_ID'])
    except (KeyError, slacker.Error):
        message = 'There was an error accessing the Slack API'
    else:
        if response.successful:
            messages = response.body.get('messages', [])
            requests.post(response_url, data=json.dumps({'text': 'Scraping...'}))
            results = scrape_function(messages)
            album_ids = models.check_for_new_list_ids(results)
            try:    
                if album_ids:
                    callback(album_ids)
            except models.DatabaseError as e:
                message = 'Failed to update list'
                print "[db]: failed to perform %s" % callback.func_name
                print "[db]: %s" % e
            else:
                message = 'Finished checking for new albums: %d found.' % (len(album_ids), )
        else:
            message = 'Failed to get channel history'
    if response_url:
        requests.post(
            response_url,
            data=json.dumps(
                {'text': message}
            )
        )


@delayed.queue_func
def deferred_consume(text, scrape_function, callback, response_url=DOOM_BOT_URL):
    try:
        album_id = scrape_function(text)
    except scrapers.NotFoundError:
        message = None
    else:
        try:
            if album_id not in models.get_list():
                try:    
                    callback(album_id)
                except models.DatabaseError as e:
                    message = 'Failed to update list'
                    print "[db]: failed to perform %s" % callback.func_name
                    print "[db]: %s" % e
                else:
                    message = 'Added album to list'
                    deferred_process_album_details.delay(album_id)
            else:
                message = 'Album already in list'
        except models.DatabaseError as e:
            print "[db]: failed to check existing items"
            print "[db]: %s" % e
    if response_url and message is not None:
        requests.post(
            response_url,
            data=message
        )


@delayed.queue_func
def deferred_process_all_album_details(response_url=DOOM_BOT_URL):
    def get_album_details_from_ids():
        for album_id in models.check_for_new_albums():
            try:
                album, artist = scrapers.scrape_album_details_from_id(album_id)
                yield (album_id, artist, album)
            except (TypeError, ValueError):
                continue
    try:
        requests.post(response_url, data=json.dumps({'text': 'Process started...'}))
        album_details = list(get_album_details_from_ids())
        models.add_many_to_albums(album_details)
    except models.DatabaseError as e:
        print "[db]: failed to add album details"
        print "[db]: %s" % e
        message = 'Failed to process all album details...'
    else:
        message = 'Processed all album details: %d found.' % (len(album_details), )
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_process_album_details(album_id):
    try:
        album, artist, url = scrapers.scrape_album_details_from_id(album_id)
        models.add_to_albums(album_id, artist, album, url)
    except models.DatabaseError as e:
        print "[db]: failed to add album details"
        print "[db]: %s" % e
    except (TypeError, ValueError):
        pass


@app.route('/consume', methods=['POST'])
def consume():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        channel = form_data.get('channel_name', 'doom')
        deferred_consume.delay(
            form_data.get('text', ''),
            scrapers.scrape_bandcamp_album_ids_from_url,
            models.add_to_list,
            response_url=BOT_URL_TEMPLATE.format(channel=channel),
        )
    return '', 200


@app.route('/consume/all', methods=['POST'])
def consume_all():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        channel = form_data.get('channel_name', 'doom')
        response_url = BOT_URL_TEMPLATE.format(channel=channel)
        contents = form_data.get('text', '')
        for url in re.findall(URL_REGEX, contents):
            print "[debug]: " + url
            if 'bandcamp' in url:
                deferred_consume.delay(
                    url,
                    scrapers.scrape_bandcamp_album_ids_from_url,
                    models.add_to_list,
                    response_url=response_url,
                )
    return '', 200


@app.route('/list', methods=['GET'])
@app.cache.cached(timeout=60 * 60)
def list_albums():
    try:
        response = flask.Response(json.dumps(models.get_list()))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/list/count', methods=['GET'])
@app.cache.cached(timeout=60)
def id_count():
    try:
        response = flask.Response(json.dumps({'count': models.get_list_count()}))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/albums', methods=['GET'])
@app.cache.cached(timeout=60 * 60)
def list_album_details():
    try:
        details = [
            {
                album_id: {
                    'artist': artist,
                    'album': album,
                    'url': url,
                }
            }
            for album_id, album, artist, url in models.get_albums()
        ]
        response = flask.Response(json.dumps(details))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/albums/count', methods=['GET'])
@app.cache.cached(timeout=60)
def count_albums():
    try:
        response = flask.Response(json.dumps({'count': models.get_albums_count()}))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/albums/dump', methods=['GET'])
@app.cache.cached(timeout=60 * 30)
def dump_album_details():
    csv_file = StringIO.StringIO()
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['id', 'album', 'artist', 'url'])
    for album_id, album, artist, url in models.get_albums():
        csv_writer.writerow([album_id, album, artist, url])
    csv_file.seek(0)
    return flask.send_file(csv_file, attachment_filename="doom.csv", as_attachment=True)


@app.route('/count', methods=['POST'])
def album_count():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        return str(models.get_albums_count()), 200
    return '', 200


@app.route('/logs', methods=['GET'])
def list_logs():
    try:
        response = flask.Response(json.dumps(models.get_logs()))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    return response


@app.route('/delete', methods=['POST'])
def delete():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        album_id = form_data.get('text')
        if album_id:
            try:
                models.delete_album(album_id.strip())
            except models.DatabaseError:
                return 'Failed to delete album', 200
            else:
                return 'Deleted album', 200
    return '', 200


@app.route('/add', methods=['POST'])
def add():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        album_id = form_data.get('text')
        if album_id:
            try:
                models.add_to_list(album_id.strip())
            except models.DatabaseError:
                return 'Failed to add new album', 200
            else:
                return 'Added new album', 200
    return '', 200


@app.route('/scrape', methods=['POST'])
def scrape():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        deferred_scrape.delay(
            scrapers.scrape_bandcamp_album_ids_from_messages,
            models.add_many_to_list,
            form_data.get('response_url', DOOM_BOT_URL),
        )
        return 'Scrape request sent', 200
    return '', 200


@app.route('/proc', methods=['POST'])
def proc():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        deferred_process_all_album_details.delay(
            form_data.get('response_url', DOOM_BOT_URL)
        )
        return 'Process request sent', 200
    return '', 200


@app.route('/album/<album_id>', methods=['GET'])
def album(album_id):
    try:
        response = flask.Response(json.dumps({
            'text': 'Success',
            'album': dict(zip(
                ('id', 'name', 'artist', 'url'),
                models.get_album_details(album_id),
            ))
        }))
    except (models.DatabaseError, TypeError):
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/bc/<album_id>', methods=['GET'])
def bc(album_id):
    return flask.redirect(BANDCAMP_URL_TEMPLATE.format(album_id=album_id), code=302)


@app.route('/link', methods=['POST'])
def link():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        album_id = form_data.get('text')
        if not album_id:
            return 'Provide an album ID', 200
        try:
            _, _, _, url = models.get_album_details(album_id)
        except models.DatabaseError:
            return 'Doomlist error - check with admin', 200
        except TypeError:
            return 'Album not found in the Doomlist', 200
        else:
            response = {
                "response_type": "in_channel",
                "text": url,
                "unfurl_links": "true",
            }
            return flask.Response(json.dumps(response), mimetype='application/json')
    return '', 200


@app.route('/random', methods=['POST'])
def random_album():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        try:
            _, _, _, url = models.get_random_album()
        except models.DatabaseError:
            return 'Doomlist error - check with admin', 200
        except TypeError:
            return 'No album found in the Doomlist', 200
        else:
            response_type = 'in_channel' if 'post' in form_data.get('text', '') else 'ephemeral'
            response = {
                "response_type": response_type,
                "text": url,
                "unfurl_links": "true",
            }
            return flask.Response(json.dumps(response), mimetype='application/json')
    return '', 200


def build_search_response(albums):
    return {
        "text": "Your search returned {} results".format(len(albums)),
        "attachments": [
            {
                "fallback": "{} by {}".format(album[1], album[2]),
                "color": "#36a64f",
                "pretext": "{} by {}".format(album[1], album[2]),
                "author_name": album[2],
                "title": album[1],
                "title_link": album[3],
                "fields": [
                    {
                        "title": "Album ID",
                        "value": album[0],
                        "short": 'false',
                    }
                ],
                "footer": "Doomlist",
            }
            for album in albums
        ]
    }


@app.route('/search', methods=['POST'])
def search():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        query = form_data.get('text')
        if query:
            try:
                albums = models.search_albums(query)
            except models.DatabaseError:
                return 'Failed to perform search', 200
            else:
                response = build_search_response(albums)
                return flask.Response(json.dumps(response), mimetype='application/json')
    return '', 200


@app.route('/votes', methods=['GET'])
@app.cache.cached(timeout=60 * 5)
def all_votes():
    try:
        results = [
            dict(zip(('id', 'artist', 'album', 'votes'), details))
            for details in models.get_votes()
        ]
        response = flask.Response(json.dumps({
            'text': 'Success', 
            'value': results,
        }))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/votes/<album_id>', methods=['GET'])
def votes(album_id):
    try:
        response = flask.Response(json.dumps({
            'text': 'Success', 
            'value': models.get_votes_count(album_id),
        }))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/vote', methods=['POST'])
def vote():
    form_data = flask.request.form
    try:
        album_id = form_data['album_id']
        models.add_to_votes(album_id)
        response = flask.Response(json.dumps({
            'text': 'Success', 
            'value': models.get_votes_count(album_id),
        }))
    except (models.DatabaseError, KeyError):
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/top', methods=['GET'])
@app.cache.cached(timeout=60 * 5)
def top():
    try:
        results = [
            dict(zip(('id', 'artist', 'album', 'votes'), details))
            for details in models.get_top_votes()
        ]
        response = flask.Response(json.dumps({
            'text': 'Success', 
            'value': results,
        }))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))   
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


if __name__ == "__main__":
    app.run(debug=os.environ.get('DEBUG', True))

