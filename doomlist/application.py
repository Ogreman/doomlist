import re
import os
import json
import collections
import datetime
import requests
import flask
import slacker
import csv
import functools
import io

from doomlist.scrapers import scrapers
from doomlist.delayed import delayed
from doomlist.models import DatabaseError
from doomlist.models import albums as albums_model, tags as tags_model, list as list_model

from flask_cacheify import init_cacheify
from pathlib import Path


TEMPLATE_DIR = Path(__file__).parent.joinpath('templates')

app = flask.Flask(__name__, template_folder=TEMPLATE_DIR)
app.config.from_object(os.environ['APP_SETTINGS'])
app.cache = init_cacheify(app)

LIST_NAME = app.config['LIST_NAME']
API_TOKEN = app.config['SLACK_API_TOKEN']
CLIENT_ID = app.config['SLACK_CLIENT_ID']
CLIENT_SECRET = app.config['SLACK_CLIENT_SECRET']
SLACK_TEAM = app.config['SLACK_TEAM']
BOT_URL_TEMPLATE = app.config['BOT_URL_TEMPLATE']
DEFAULT_CHANNEL = app.config['DEFAULT_CHANNEL']
SLACKBOT_TOKEN = app.config['SLACKBOT_TOKEN']
BOT_URL_TEMPLATE = BOT_URL_TEMPLATE.format(team=SLACK_TEAM, token=SLACKBOT_TOKEN, channel='{channel}')
BOT_URL = BOT_URL_TEMPLATE.format(channel=DEFAULT_CHANNEL)
ADMIN_IDS = app.config['ADMIN_IDS']
APP_TOKENS = app.config['APP_TOKENS']
URL_REGEX = 'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
HASHTAG_REGEX = '#(?:[a-zA-Z]|[0-9]|[-_.+])+'
BANDCAMP_URL_TEMPLATE = 'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/artwork=small'
SLACK_AUTH_URL = 'https://slack.com/api/oauth.access?client_id={client_id}&client_secret={client_secret}&code={code}'

db_error_message = '{name} error - check with admin'.format(name=LIST_NAME)
not_found_message = 'Album not found in the {name}'.format(name=LIST_NAME)


def get_and_set_album_details(album_id):
    try:
        details = albums_model.get_album_details(album_id)
    except DatabaseError as e:
        app.cache.delete('alb-' + album_id)
        raise e
    else:
        app.cache.set('alb-' + album_id, details, 60 * 15)
    return details


def get_cached_album_details(album_id):
    return app.cache.get('alb-' + album_id) or get_and_set_album_details(album_id)


def admin_only(func):
    """
    Decorator for locking down slack endpoints to admins
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if flask.request.form.get('user_id', '') in ADMIN_IDS or app.config['DEBUG']:
            return func(*args, **kwargs)
        print('[access]: failed admin-only test')
        return '', 403
    return wraps


def not_bots(func):
    """
    Decorator for preventing triggers by bots
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if 'bot_id' not in flask.request.form:
            return func(*args, **kwargs)
        print('[access]: failed not-bot test')
        return '', 200
    return wraps


def slack_check(func):
    """
    Decorator for locking down slack endpoints to registered apps only
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if flask.request.form.get('token', '') in APP_TOKENS or app.config['DEBUG']:
            return func(*args, **kwargs)
        print('[access]: failed slack-check test')
        return '', 403
    return wraps


def allow_all(func):
    """
    Decorator for adding * to 'Access-Control-Allow-Origin'
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        response = func(*args, **kwargs)
        if hasattr(response, 'headers'):
            response.headers['Access-Control-Allow-Origin'] = '*'
        return response
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
            album_ids = list_model.check_for_new_list_ids(results)
            try:    
                if album_ids:
                    callback(album_ids)
            except DatabaseError as e:
                message = 'failed to update list'
                print(f'[db]: failed to perform {callback.__name__}')
                print(f'[db]: {e}')
            else:
                message = 'Finished checking for new albums: %d found.' % (len(album_ids), )
        else:
            message = 'failed to get channel history'
    if response_url:
        requests.post(
            response_url,
            data=json.dumps(
                {'text': message}
            )
        )


@delayed.queue_func
def deferred_consume(text, scrape_function, callback, response_url=BOT_URL, channel='', tags=None):
    try:
        album_id = scrape_function(text)
    except scrapers.NotFoundError:
        message = None
    else:
        try:
            if album_id not in list_model.get_list():
                try:    
                    callback(album_id)
                except DatabaseError as e:
                    message = 'failed to update list'
                    print(f'[db]: failed to perform {callback.__name__}')
                    print(f'[db]: {e}')
                else:
                    message = 'Added album to list: ' + str(album_id)
                    deferred_process_album_details.delay(str(album_id), channel)
            else:
                message = 'Album already in list: ' + str(album_id)
            if tags:
                deferred_process_tags.delay(str(album_id), tags)
        except DatabaseError as e:
            print('[db]: failed to check existing items')
            print(f'[db]: {e}')
    if response_url and message is not None:
        requests.post(response_url, data=message)


@delayed.queue_func
def deferred_process_tags(album_id, tags):
    for tag in tags:
        tag = tag[1:] if tag.startswith('#') else tag
        try:
            if tag not in tags_model.get_tags():
                tags_model.add_to_tags(tag)
            tags_model.tag_album(album_id, tag)
        except DatabaseError as e:
            print(f'[db]: failed to add tag "{tag}" to album {album_id}')
            print(f'[db]: {e}')
        else:
            print(f'Tagged {album_id} with "{tag}"')


@delayed.queue_func
def deferred_process_all_album_details(response_url=BOT_URL):
    try:
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Process started...'}))
        for album_id in albms.check_for_new_albums():
            deferred_process_album_details.delay(album_id)
    except DatabaseError as e:
        print('[db]: failed to check for new album details')
        print(f'[db]: {e}')
        message = 'failed to process all album details...'
    else:
        message = 'Processed all album details'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_clear_cache(response_url=BOT_URL):
    app.cache.clear()
    if response_url:
        requests.post(response_url, data=json.dumps({'text': 'Cache cleared'}))


@delayed.queue_func
def deferred_delete(album_id, response_url=BOT_URL):
    try:
        albums_model.delete_from_list_and_albums(album_id)
        app.cache.delete(f'alb-{album_id}')
    except DatabaseError as e:
        print(f'[db]: failed to delete album details for {album_id}')
        print(f'[db]: {e}')
        message = f'failed to delete album details for {album_id}'
    else:
        print(f'[db]: deleted album details for {album_id}')
        message = f'Removed album from list: {album_id}'
    if response_url:
        requests.post(response_url, data=message)


@delayed.queue_func
def deferred_process_album_details(album_id, channel=''):
    try:
        album, artist, url = scrapers.scrape_album_details_from_id(album_id)
        albums_model.add_to_albums(album_id, artist, album, url, channel=channel)
        deferred_process_album_cover.delay(album_id)
    except DatabaseError as e:
        print(f'[db]: failed to add album details for {album_id}')
        print(f'[db]: {e}')
    except (TypeError, ValueError):
        pass
    else:
        print(f'[scraper]: processed album details for {album_id}')


@delayed.queue_func
def deferred_process_album_cover(album_id):
    try:
        _, _, _, album_url, _, _, _, _ = get_cached_album_details(album_id)
        album_cover_url = scrapers.scrape_album_cover_url_from_url(album_url)
        albums_model.add_img_to_album(album_id, album_cover_url)
    except DatabaseError as e:
        print(f'[db]: failed to add album cover for {album_id}')
        print(f'[db]: {e}')
    except scrapers.NotFoundError as e:
        print(f'[scraper]: failed to find album art for {album_id}')
        print(f'[scraper]: {e}')
    except (TypeError, ValueError):
        pass
    else:
        print(f'[scraper]: processed cover for {album_id}')


@delayed.queue_func
def deferred_process_all_album_covers(response_url=BOT_URL):
    try:
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Process started...'}))
        for album_id in [alb[0] for alb in albums_model.get_albums() if not alb[4]]:
            deferred_process_album_cover.delay(album_id)
    except DatabaseError as e:
        print('[db]: failed to get all album details')
        print(f'[db]: {e}')
        message = 'failed to process all album details...'
    else:
        message = 'Processed all album covers'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_check_album_url(album_id):
    try:
        _, _, _, album_url, _, available, _, _ = get_cached_album_details(album_id)
        response = requests.head(album_url)
        if response.ok and not available:
            albums_model.update_album_availability(album_id, True)
        elif response.status_code > 400 and available:
            albums_model.update_album_availability(album_id, False)
            print(f'[scraper]: {album_id} no longer available')
    except DatabaseError as e:
        print('[db]: failed to update album after check')
        print(f'[db]: {e}')
    except (TypeError, ValueError):
        pass
    else:
        print(f'[scraper]: checked availability for {album_id}')


@delayed.queue_func
def deferred_check_all_album_urls(response_url=BOT_URL):
    try:
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Check started...'}))
        for album_id in albums_model.get_album_ids():
            deferred_check_album_url.delay(album_id)
    except DatabaseError as e:
        print('[db]: failed to check for new album details')
        print(f'[db]: {e}')
        message = 'failed to check all album urls...'
    else:
        message = 'Finished checking all album URLs'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@app.route('/slack/spoiler', methods=['POST'])
@slack_check
def spoiler():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    user = form_data['user_name']
    text = form_data['text']
    url = form_data.get('response_url', BOT_URL_TEMPLATE.format(channel=channel))
    requests.post(url, data=json.dumps({
        'text': user + ' posted a spoiler...',
        'attachments': [
            {
                'text': '\n\n\n\n\n\n\n' + text,
                'color': 'danger',
                'unfurl_links': 'false',
                'unfurl_media': 'false',
            },
        ],
        'response_type': 'in_channel'}))
    return '', 200


@app.route('/slack/consume', methods=['POST'])
@slack_check
@not_bots
def consume():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    deferred_consume.delay(
        form_data.get('text', ''),
        scrapers.scrape_bandcamp_album_ids_from_url,
        list_model.add_to_list,
        response_url=BOT_URL_TEMPLATE.format(channel=channel),
        channel=channel
    )
    return '', 200


@app.route('/slack/consume/all', methods=['POST'])
@slack_check
def consume_all():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    response_url = BOT_URL_TEMPLATE.format(channel=channel)
    contents = form_data.get('text', '')
    tags = re.findall(HASHTAG_REGEX, contents)
    for url in re.findall(URL_REGEX, contents):
        if 'bandcamp' in url:
            deferred_consume.delay(
                url,
                scrapers.scrape_bandcamp_album_ids_from_url,
                list_model.add_to_list,
                response_url=response_url,
                channel=channel,
                tags=tags
            )
        elif 'youtube' in url or 'youtu.be' in url:
            requests.post(response_url, data='YouTube scraper not yet implemented')
        elif 'soundcloud' in url:
            requests.post(response_url, data='Soundcloud scraper not yet implemented')
    return '', 200


@app.route('/slack/count', methods=['POST'])
@slack_check
def album_count():
    return str(albums_model.get_albums_count()), 200


@app.route('/slack/delete', methods=['POST'])
@slack_check
@admin_only
def delete():
    form_data = flask.request.form
    album_id = form_data.get('text')
    channel = form_data.get('channel_name', 'chat')
    if album_id:
        response_url = BOT_URL_TEMPLATE.format(channel=channel)
        deferred_delete.delay(album_id.strip(), response_url)
    return '', 200


@app.route('/slack/add', methods=['POST'])
@slack_check
def add():
    form_data = flask.request.form
    album_id = form_data.get('text')
    if album_id:
        try:
            list_model.add_to_list(album_id.strip())
        except DatabaseError as e:
            print('[db]: failed to add new album')
            print(f'[db]: {e}')
            return 'failed to add new album', 200
        else:
            return 'Added new album', 200
    return '', 200


@app.route('/slack/clear', methods=['POST'])
@slack_check
@admin_only
def clear_cache():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url', BOT_URL)
    deferred_clear_cache.delay(response)
    return 'Clear cache request sent', 200


@app.route('/slack/scrape', methods=['POST'])
@slack_check
@admin_only
def scrape():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url', BOT_URL)
    deferred_scrape.delay(
        scrapers.scrape_bandcamp_album_ids_from_messages,
        list_model.add_many_to_list,
        response
    )
    return 'Scrape request sent', 200


@app.route('/slack/check', methods=['POST'])
@slack_check
@admin_only
def check_urls():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url', BOT_URL)
    deferred_check_all_album_urls.delay(response)
    return 'Check request sent', 200


@app.route('/slack/process', methods=['POST'])
@slack_check
@admin_only
def process():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url', BOT_URL)
    deferred_process_all_album_details.delay(response)
    return 'Process request sent', 200


@app.route('/slack/process/covers', methods=['POST'])
@slack_check
@admin_only
def covers():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url', BOT_URL)
    deferred_process_all_album_covers.delay(response)
    return 'Process request sent', 200


@app.route('/slack/link', methods=['POST'])
@slack_check
def link():
    form_data = flask.request.form
    album_id = form_data.get('text')
    if not album_id:
        return 'Provide an album ID', 200
    try:
        _, _, _, url, _, _, _, _ = get_cached_album_details(album_id)
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return db_error_message, 200
    except TypeError as e:
        print(f'[slack]: no album found for link: {e}')
        return not_found_message, 200
    else:
        response = {
            'response_type': 'in_channel',
            'text': url,
            'unfurl_links': 'true',
        }
        return flask.Response(json.dumps(response), mimetype='application/json')


@app.route('/slack/random', methods=['POST'])
@slack_check
def random_album():
    form_data = flask.request.form
    try:
        _, _, _, url, img = albums_model.get_random_album()
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return db_error_message, 200
    except TypeError as e:
        print(f'[slack]: no album found for random: {e}')
        return not_found_message, 200
    else:
        response_type = 'in_channel' if 'post' in form_data.get('text', '') else 'ephemeral'
        response = {
            'response_type': response_type,
            'text': url,
            'unfurl_links': 'true',
        }
        return flask.Response(json.dumps(response), mimetype='application/json')


def build_search_response(details):
    attachments = []
    for album_id, d in details.items():
        tag_actions = [
            {
                'name': 'tag',
                'text': f'#{tag}',
                'type': 'button',
                'value': str(tag),
            }
            for i, tag in enumerate(d['tags'])
        ]
        attachment = {
            'fallback': f'{d["album"]} by {d["artist"]}',
            'color': '#36a64f',
            'pretext': f'{d["album"]} by {d["artist"]}',
            'author_name': d['artist'],
            'image_url': d['img'],
            'title': d['album'],
            'title_link': d['url'],
            'callback_id': f'album_results_{album_id}',
            'fields': [
                {
                    'title': 'Album ID',
                    'value': album_id,
                    'short': 'false',
                },
                {
                        'title': 'Tags',
                        'value': ', '.join(d['tags']),
                        'short': 'false',
                },
            ],
            'actions': [
                {
                    'name': 'album',
                    'text': 'Post',
                    'type': 'button',
                    'value': d['url'],
                }
            ] + tag_actions,
            'footer': LIST_NAME,
        }
        attachments.append(attachment)

    return {
        'text': f'Your search returned {len(details)} results',
        'attachments': attachments,
    }


@app.route('/slack/search', methods=['POST'])
@slack_check
def search():
    form_data = flask.request.form
    query = form_data.get('text')
    if query:
        response = app.cache.get(f'q-{query}')
        if not response:
            func = functools.partial(albums_model.search_albums, query)
            try:
                details = build_album_details(func)
            except DatabaseError as e:
                print('[db]: failed to build album details')
                print(f'[db]: {e}')
                return 'failed to perform search', 200
            else:
                response = build_search_response(details)
                app.cache.set(f'q-{query}', response, 60 * 15)
        return flask.Response(json.dumps(response), mimetype='application/json')
    return '', 200


@app.route('/slack/tags', methods=['POST'])
@slack_check
def search_tags():
    form_data = flask.request.form
    query = form_data.get('text')
    if query:
        response = app.cache.get(f't-{query}')
        if not response:
            func = functools.partial(albums_model.search_albums_by_tag, query)
            try:
                details = build_album_details(func)
            except DatabaseError as e:
                print('[db]: failed to build album details')
                print(f'[db]: {e}')
                return 'failed to perform search', 200
            else:
                response = build_search_response(details)
                app.cache.set(f't-{query}', response, 60 * 15)
        return flask.Response(json.dumps(response), mimetype='application/json')
    return '', 200


@app.route('/slack/search/button', methods=['POST'])
def button():
    try:
        form_data = json.loads(flask.request.form['payload'])
    except KeyError:
        print('[slack]: payload missing from button')
        return '', 200
    if form_data.get('token') not in APP_TOKENS:
        print('[access]: button failed slack test')
        return '', 200
    try:
        action = form_data['actions'][0]
        if 'tag' in action['name']:
            query = action['value']
            search_response = app.cache.get(f't-{query}')
            if not search_response:
                func = functools.partial(albums_model.search_albums_by_tag, query)
                try:
                    details = build_album_details(func)
                except DatabaseError as e:
                    print('[db]: failed to build album details')
                    print(f'[db]: {e}')
                    return 'failed to perform search', 200
                else:
                    search_response = build_search_response(details)
                    app.cache.set(f't-{query}', search_response, 60 * 15)
            response = {
                'response_type': 'ephemeral',
                'text': f'Your #{query} results',
                'replace_original': 'false',
                'unfurl_links': 'true',
                'attachments': search_response['attachments'],
            }
            return flask.Response(json.dumps(response), mimetype='application/json')
        elif 'album' in action['name']:
            url = action['value']
            user = form_data['user']['name']
            message = f'{user} posted {url} from the {LIST_NAME}'
            response = {
                'response_type': 'in_channel',
                'text': message,
                'replace_original': False,
                'unfurl_links': 'true',
            }
            return flask.Response(json.dumps(response), mimetype='application/json')
    except KeyError as e:
        print(f'[slack]: failed to build results: {e}')
        return db_error_message, 200
    return '', 200


@app.route('/api/list', methods=['GET'])
@app.cache.cached(timeout=60 * 60)
@allow_all
def api_list_albums():
    try:
        response = flask.Response(json.dumps(list_model.get_list()))
    except DatabaseError as e:
        print('[db]: failed to get list')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


@app.route('/api/list/count', methods=['GET'])
@app.cache.cached(timeout=60)
@allow_all
def api_id_count():
    try:
        response = flask.Response(json.dumps({'count': list_model.get_list_count()}))
    except DatabaseError as e:
        print('[db]: failed to get list count')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


def build_album_details(func):
    details = collections.defaultdict(lambda: {
        'artist': '',
        'album': '',
        'url': '',
        'img': '',
        'channel': '',
        'added': '',
        'tags': []
    })
    for album_id, album, artist, url, img, channel, added, tag in func():
        if album_id not in details:
            details[album_id]['artist'] = artist
            details[album_id]['album'] = album
            details[album_id]['url'] = url
            details[album_id]['img'] = img if img else ''
            details[album_id]['channel'] = channel
            details[album_id]['added'] = added.isoformat()
        if tag:
            details[album_id]['tags'].append(tag)
    return details


@app.route('/api/albums', methods=['GET'])
@allow_all
def api_list_album_details():
    channel = flask.request.args.get('channel')
    if channel:
        get_func = functools.partial(albums_model.get_albums_by_channel_with_tags, channel)
        key = f'api-albums-{channel}'
    else:
        get_func = albums_model.get_albums_with_tags
        key = 'api-albums'
    try:
        details = app.cache.get(key)
        if not details:
            details = build_album_details(get_func)
            details = [{key: d} for key, d in details.items()]
            app.cache.set(key, details, 60 * 30)
        response = flask.Response(json.dumps(details))
    except DatabaseError as e:
        print('[db]: failed to get albums')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


@app.route('/api/albums/count', methods=['GET'])
@app.cache.cached(timeout=60)
@allow_all
def api_count_albums():
    try:
        response = flask.Response(json.dumps({'count': albums_model.get_albums_count()}))
    except DatabaseError as e:
        print('[db]: failed to get albums count')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


@app.route('/api/albums/dump', methods=['GET'])
@app.cache.cached(timeout=60 * 30)
def api_dump_album_details():
    # need StringIO for csv.writer
    proxy = io.StringIO()
    csv_writer = csv.writer(proxy)
    csv_writer.writerow(['id', 'album', 'artist', 'url', 'img', 'available', 'channel', 'added'])
    for album_id, album, artist, url, img, available, channel, added in albums_model.get_albums():
        csv_writer.writerow([album_id, album, artist, url, img, available, channel, added.isoformat()])
    # and BytesIO for flask.send_file
    mem = io.BytesIO()
    mem.write(proxy.getvalue().encode('utf-8'))
    mem.seek(0)
    proxy.close()
    # see: https://stackoverflow.com/a/45111660
    return flask.send_file(mem, as_attachment=True, attachment_filename="albums.csv", mimetype='text/csv')


@app.route('/api/album/<album_id>', methods=['GET'])
@allow_all
def api_album(album_id):
    try:
        album_id, album, artist, url, img, available, channel, added = get_cached_album_details(album_id)
        response = flask.Response(json.dumps({
            'text': 'success',
            'album': dict(zip(
                ('id', 'name', 'artist', 'url', 'img', 'available', 'channel', 'added'),
                (album_id, album, artist, url, img, available, channel, added.isoformat()),
            ))
        }))
    except TypeError:
        response = flask.Response(json.dumps({'text': 'not found'}))
    except DatabaseError as e:
        print(f'[db]: failed to get album: {album_id}')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


@app.route('/api/tags', methods=['GET'])
@allow_all
def api_tags():
    try:
        response = flask.Response(json.dumps({'text': 'success',
            'tags': [tag for tag in tags_model.get_tags()]}))
    except DatabaseError as e:
        print('[db]: failed to get tags')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


# @app.route('/api/tags/count', methods=['GET'])
# def api_tags():
#     try:
#         response = flask.Response(json.dumps({'text': 'success',
#             'tags': [tag for tag in models.get_tags()]}))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


@app.route('/api/tags/<tag>', methods=['GET'])
@allow_all
def api_album_by_tag(tag):
    get_func = functools.partial(albums_model.get_albums_by_tag, tag)
    key = f'api-tags-{tag}'
    try:
        details = app.cache.get(key)
        if not details:
            details = build_album_details(get_func)
            details = [{key: d} for key, d in details.items()]
            app.cache.set(key, details, 60 * 30)
        response = flask.Response(json.dumps(details))
    except DatabaseError as e:
        print(f'[db]: failed to get tag: {tag}')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


@app.route('/api/bc/<album_id>', methods=['GET'])
def api_bc(album_id):
    return flask.redirect(BANDCAMP_URL_TEMPLATE.format(album_id=album_id), code=302)


@app.route('/api/albums/random', methods=['GET'])
@allow_all
def api_random():
    try:
        album_id, name, artist, album_url, img = albums_model.get_random_album()
        response = flask.Response(json.dumps({
            'text': 'success',
            'album': dict(zip(
                ('id', 'name', 'artist', 'url', 'img'),
                (album_id, name, artist, album_url, img),
            ))
        }))
    except TypeError:
        response = flask.Response(json.dumps({'text': 'not found'}))
    except DatabaseError as e:
        print(f'[db]: failed to get album: {album_id}')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


@app.route('/api/albums/available/urls', methods=['GET'])
@allow_all
def available_urls():
    try:
        key = 'api-albums-available-urls'
        details = app.cache.get(key)
        if not details:
            details = [album[3] for album in albums_model.get_albums_available()]
            app.cache.set(key, details, 60 * 30)
        response = flask.Response(json.dumps(details))
    except DatabaseError as e:
        print('[db]: failed to get album urls')
        print(f'[db]: {e}')
        response = flask.Response(json.dumps({'text': 'failed'}))
    return response


# @app.route('/api/votes', methods=['GET'])
# @app.cache.cached(timeout=60 * 5)
# def api_all_votes():
#     try:
#         results = [
#             dict(zip(('id', 'artist', 'album', 'votes'), details))
#             for details in models.get_votes()
#         ]
#         response = flask.Response(json.dumps({
#             'text': 'success', 
#             'value': results,
#         }))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


# @app.route('/api/votes/<album_id>', methods=['GET'])
# def api_votes(album_id):
#     try:
#         response = flask.Response(json.dumps({
#             'text': 'success', 
#             'value': models.get_votes_count(album_id),
#         }))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


# @app.route('/api/vote', methods=['POST'])
# def api_vote():
#     form_data = flask.request.form
#     try:
#         album_id = form_data['album_id']
#         votes.add_to_votes(album_id)
#         response = flask.Response(json.dumps({
#             'text': 'success', 
#             'value': models.get_votes_count(album_id),
#         }))
#     except (DatabaseError, KeyError):
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


# @app.route('/api/votes/top', methods=['GET'])
# @app.cache.cached(timeout=60 * 5)
# def api_top():
#     try:
#         results = [
#             dict(zip(('id', 'artist', 'album', 'votes'), details))
#             for details in models.get_top_votes()
#         ]
#         response = flask.Response(json.dumps({
#             'text': 'success', 
#             'value': results,
#         }))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))   
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     return response


# @app.route('/api/logs', methods=['GET'])
# def api_list_logs():
#     try:
#         response = flask.Response(json.dumps(models.get_logs()))
#     except DatabaseError:
#         response = flask.Response(json.dumps({'text': 'failed'}))
#     return response


@app.route('/slack/auth', methods=['GET'])
def auth():
    code = flask.request.args.get('code')
    url = SLACK_AUTH_URL.format(code=code, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    response = requests.get(url)
    print(f'[auth]: {response.json()}')
    return response.content, 200


@app.route('/', methods=['GET'])
def embedded_random():
    try:
        album_id, name, artist, album_url, _ = albums_model.get_random_album()
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return db_error_message, 500
    except TypeError:
        return not_found_message, 404
    else:
        return flask.render_template('index.html', list_name=LIST_NAME, album_id=album_id, name=name, artist=artist, album_url=album_url)


@app.route('/api', methods=['GET'])
@allow_all
def all_endpoints():
    rules = [ 
        (list(rule.methods), rule.rule) 
        for rule in app.url_map.iter_rules() 
        if rule.endpoint.startswith('api')
    ]
    response = flask.Response(json.dumps({'api': rules}))
    return response, 200
