import re
import os
import json
import datetime
import requests
import flask
import slacker
import csv
import functools
import StringIO

from scrapers import scrapers
from delayed import delayed
from models import models

from flask.ext.cacheify import init_cacheify


app = flask.Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.cache = init_cacheify(app)

LIST_NAME = app.config['LIST_NAME']
API_TOKEN = app.config['API_TOKEN']
CLIENT_ID = app.config['CLIENT_ID']
CLIENT_SECRET = app.config['CLIENT_SECRET']
SLACK_TEAM = app.config['SLACK_TEAM']
BOT_URL_TEMPLATE = app.config['BOT_URL_TEMPLATE']
DEFAULT_CHANNEL = app.config['DEFAULT_CHANNEL']
SLACKBOT_TOKEN = app.config['SLACKBOT_TOKEN']
BOT_URL_TEMPLATE = BOT_URL_TEMPLATE.format(team=SLACK_TEAM, token=SLACKBOT_TOKEN, channel="{channel}")
BOT_URL = BOT_URL_TEMPLATE.format(channel=DEFAULT_CHANNEL)
ADMIN_IDS = app.config['ADMIN_IDS']
APP_TOKENS = app.config['APP_TOKENS']
URL_REGEX = "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
BANDCAMP_URL_TEMPLATE = "https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/artwork=small"
SLACK_AUTH_URL = "https://slack.com/api/oauth.access?client_id={client_id}&client_secret={client_secret}&code={code}"

db_error_message = '{name} error - check with admin'.format(name=LIST_NAME)
not_found_message = 'Album not found in the {name}'.format(name=LIST_NAME)


def admin_only(func):
    """
    Decorator for locking down slack endpoints to admins
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if flask.request.form.get('user_id', '') in ADMIN_IDS or app.config['DEBUG']:
            return func(*args, **kwargs)
        return '', 403
    return wraps


def slack_check(func):
    """
    Decorator for locking down slack endpoints to registered apps only
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if flask.request.form.get('token', '') in APP_TOKENS or app.config['DEBUG']:
            return func(*args, **kwargs)
        return '', 403
    return wraps


@delayed.queue_func
def deferred_scrape(scrape_function, callback, response_url=BOT_URL):
    try:
        slack = slacker.Slacker(API_TOKEN)
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Getting channel history...'}))
        response = slack.channels.history(os.environ['SLACK_CHANNEL_ID'])
    except (KeyError, slacker.Error):
        message = 'There was an error accessing the Slack API'
    else:
        if response.successful:
            messages = response.body.get('messages', [])
            if response_url:
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
def deferred_consume(text, scrape_function, callback, response_url=BOT_URL):
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
                    message = 'Added album to list: ' + str(album_id)
                    deferred_process_album_details.delay(album_id)
            else:
                message = 'Album already in list: ' + str(album_id)
        except models.DatabaseError as e:
            print "[db]: failed to check existing items"
            print "[db]: %s" % e
    if response_url and message is not None:
        requests.post(
            response_url,
            data=message
        )


@delayed.queue_func
def deferred_process_all_album_details(response_url=BOT_URL):
    def get_album_details_from_ids():
        for album_id in models.check_for_new_albums():
            try:
                album, artist, url = scrapers.scrape_album_details_from_id(album_id)
                yield (album_id, artist, album, url)
            except (TypeError, ValueError):
                continue
    try:
        if response_url:
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


@app.route('/slack/consume', methods=['POST'])
@slack_check
def consume():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    deferred_consume.delay(
        form_data.get('text', ''),
        scrapers.scrape_bandcamp_album_ids_from_url,
        models.add_to_list,
        response_url=BOT_URL_TEMPLATE.format(channel=channel),
    )


@app.route('/slack/consume/all', methods=['POST'])
@slack_check
def consume_all():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    response_url = BOT_URL_TEMPLATE.format(channel=channel)
    contents = form_data.get('text', '')
    for url in re.findall(URL_REGEX, contents):
        if 'bandcamp' in url:
            deferred_consume.delay(
                url,
                scrapers.scrape_bandcamp_album_ids_from_url,
                models.add_to_list,
                response_url=response_url,
            )
        elif 'youtube' in url or 'youtu.be' in url:
            requests.post(response_url, data="YouTube scraper not yet implemented")
        elif 'soundcloud' in url:
            requests.post(response_url, data="Soundcloud scraper not yet implemented")


@app.route('/slack/count', methods=['POST'])
@slack_check
def album_count():
    return str(models.get_albums_count()), 200


@app.route('/slack/delete', methods=['POST'])
@slack_check
def delete():
    form_data = flask.request.form
    album_id = form_data.get('text')
    if album_id:
        try:
            models.delete_from_list(album_id.strip())
        except models.DatabaseError:
            return 'Failed to delete album', 200
        else:
            return 'Deleted album', 200


@app.route('/slack/add', methods=['POST'])
@slack_check
def add():
    form_data = flask.request.form
    album_id = form_data.get('text')
    if album_id:
        try:
            models.add_to_list(album_id.strip())
        except models.DatabaseError:
            return 'Failed to add new album', 200
        else:
            return 'Added new album', 200


@app.route('/slack/scrape', methods=['POST'])
@slack_check
@admin_only
def scrape():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url', BOT_URL)
    deferred_scrape.delay(
        scrapers.scrape_bandcamp_album_ids_from_messages,
        models.add_many_to_list,
        response
    )
    return 'Scrape request sent', 200


@app.route('/slack/process', methods=['POST'])
@slack_check
@admin_only
def process():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url', BOT_URL)
    deferred_process_all_album_details.delay(response)
    return 'Process request sent', 200


@app.route('/slack/link', methods=['POST'])
@slack_check
def link():
    form_data = flask.request.form
    album_id = form_data.get('text')
    if not album_id:
        return 'Provide an album ID', 200
    try:
        _, _, _, url = models.get_album_details(album_id)
    except models.DatabaseError:
        return db_error_message, 200
    except TypeError:
        return not_found_message, 200
    else:
        response = {
            "response_type": "in_channel",
            "text": url,
            "unfurl_links": "true",
        }
        return flask.Response(json.dumps(response), mimetype='application/json')


@app.route('/slack/random', methods=['POST'])
@slack_check
def random_album():
    form_data = flask.request.form
    try:
        _, _, _, url = models.get_random_album()
    except models.DatabaseError:
        return db_error_message, 200
    except TypeError:
        return not_found_message, 200
    else:
        response_type = 'in_channel' if 'post' in form_data.get('text', '') else 'ephemeral'
        response = {
            "response_type": response_type,
            "text": url,
            "unfurl_links": "true",
        }
        return flask.Response(json.dumps(response), mimetype='application/json')


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
                "callback_id": "album_results_" + album[0],
                "fields": [
                    {
                        "title": "Album ID",
                        "value": album[0],
                        "short": 'false',
                    }
                ],
                "actions": [
                    {
                        "name": "album",
                        "text": "Post",
                        "type": "button",
                        "value": album[3],
                    }
                ],
                "footer": LIST_NAME,
            }
            for album in albums
        ]
    }


@app.route('/slack/search', methods=['POST'])
@slack_check
def search():
    form_data = flask.request.form
    query = form_data.get('text')
    if query:
        try:
            albums = models.search_albums(query)
        except models.DatabaseError:
            return 'Failed to perform search', 200
        else:
            response = build_search_response(albums)
            return flask.Response(json.dumps(response), mimetype='application/json')


@app.route('/slack/search/button', methods=['POST'])
def button():
    try:
        form_data = json.loads(flask.request.form['payload'])
    except KeyError:
        return '', 200
    else:
        if form_data.get('token') in APP_TOKENS:
            try:
                url = form_data["actions"][0]["value"]
                user = form_data["user"]["name"]
                message = "{user} posted {url} from the {name}".format(user=user, url=url, name=LIST_NAME)
            except KeyError:
                return db_error_message, 200
            else:
                response = {
                    "response_type": "in_channel",
                    "text": message,
                    "replace_original": False,
                    "unfurl_links": "true",
                }
                return flask.Response(json.dumps(response), mimetype='application/json')
    return '', 200


@app.route('/api/list', methods=['GET'])
@app.cache.cached(timeout=60 * 60)
def list_albums():
    try:
        response = flask.Response(json.dumps(models.get_list()))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/api/list/count', methods=['GET'])
@app.cache.cached(timeout=60)
def id_count():
    try:
        response = flask.Response(json.dumps({'count': models.get_list_count()}))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/api/albums', methods=['GET'])
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


@app.route('/api/albums/count', methods=['GET'])
@app.cache.cached(timeout=60)
def count_albums():
    try:
        response = flask.Response(json.dumps({'count': models.get_albums_count()}))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/api/albums/dump', methods=['GET'])
@app.cache.cached(timeout=60 * 30)
def dump_album_details():
    csv_file = StringIO.StringIO()
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(['id', 'album', 'artist', 'url'])
    for album_id, album, artist, url in models.get_albums():
        csv_writer.writerow([album_id, album, artist, url])
    csv_file.seek(0)
    return flask.send_file(csv_file, attachment_filename="albums.csv", as_attachment=True)


@app.route('/api/album/<album_id>', methods=['GET'])
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


@app.route('/api/bc/<album_id>', methods=['GET'])
def bc(album_id):
    return flask.redirect(BANDCAMP_URL_TEMPLATE.format(album_id=album_id), code=302)


@app.route('/api/votes', methods=['GET'])
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


@app.route('/api/votes/<album_id>', methods=['GET'])
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


@app.route('/api/vote', methods=['POST'])
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


@app.route('/api/top', methods=['GET'])
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


@app.route('/api/logs', methods=['GET'])
def list_logs():
    try:
        response = flask.Response(json.dumps(models.get_logs()))
    except models.DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    return response


@app.route('/slack/auth', methods=['GET'])
def auth():
    code = flask.request.args.get('code')
    url = SLACK_AUTH_URL.format(code=code, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    response = requests.get(url)
    print "[auth]: " + str(response.json())
    return response.content, 200


if __name__ == "__main__":
    app.run(debug=app.config.get('DEBUG', True))

