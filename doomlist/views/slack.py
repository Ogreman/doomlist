import flask
import functools
import json
import re
import requests
import slacker

from doomlist import constants
from doomlist.delayed import queued
from doomlist.models import DatabaseError
from doomlist.models import albums as albums_model, tags as tags_model, list as list_model
from doomlist.scrapers import bandcamp, links
from doomlist.views import build_album_details


slack_blueprint = flask.Blueprint(name='slack',
                               import_name=__name__,
                               url_prefix='/slack')


@slack_blueprint.before_request
def before_request():
    print('slack request')
    if flask.request.form.get('token', '') in APP_TOKENS or app.config['DEBUG']:
        print('[access]: failed slack-check test')
        flask.abort(403)


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
        return '', 403
    return wraps


@slack_blueprint.route('/spoiler', methods=['POST'])
def spoiler():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    user = form_data['user_name']
    text = form_data['text']
    bot_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=channel)
    url = form_data.get('response_url', bot_url)
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


@slack_blueprint.route('/consume', methods=['POST'])
@not_bots
def consume():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    bot_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=channel)
    queued.deferred_consume.delay(
        form_data.get('text', ''),
        bandcamp.scrape_bandcamp_album_ids_from_url,
        list_model.add_to_list,
        response_url=bot_url,
        channel=channel
    )
    return '', 200


@slack_blueprint.route('/consume/all', methods=['POST'])
def consume_all():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    bot_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=channel)
    contents = form_data.get('text', '')
    tags = re.findall(constants.HASHTAG_REGEX, contents)
    for url in links.scrape_links_from_text(contents):
        if 'bandcamp' in url:
            queued.deferred_consume.delay(
                url,
                bandcamp.scrape_bandcamp_album_ids_from_url,
                list_model.add_to_list,
                response_url=bot_url,
                channel=channel,
                tags=tags
            )
        elif 'youtube' in url or 'youtu.be' in url:
            requests.post(bot_url, data='YouTube scraper not yet implemented')
        elif 'soundcloud' in url:
            requests.post(bot_url, data='Soundcloud scraper not yet implemented')
    return '', 200


@slack_blueprint.route('/count', methods=['POST'])
def album_count():
    return str(albums_model.get_albums_count()), 200


@slack_blueprint.route('/delete', methods=['POST'])
@admin_only
def delete():
    form_data = flask.request.form
    album_id = form_data.get('text')
    channel = form_data.get('channel_name', 'chat')
    if album_id:
        bot_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=channel)
        queued.deferred_delete.delay(album_id.strip(), bot_url)
    return '', 200


@slack_blueprint.route('/add', methods=['POST'])
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


@slack_blueprint.route('/clear', methods=['POST'])
@admin_only
def clear_cache():
    form_data = flask.request.form
    default_channel = flask.current_app.config['DEFAULT_CHANNEL']
    response_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_clear_cache.delay(response)
    return 'Clear cache request sent', 200


@slack_blueprint.route('/scrape', methods=['POST'])
@admin_only
def scrape():
    form_data = flask.request.form
    default_channel = flask.current_app.config['DEFAULT_CHANNEL']
    response_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_scrape.delay(
        bandcamp.scrape_bandcamp_album_ids_from_messages,
        list_model.add_many_to_list,
        response
    )
    return 'Scrape request sent', 200


@slack_blueprint.route('/check', methods=['POST'])
@admin_only
def check_urls():
    form_data = flask.request.form
    default_channel = flask.current_app.config['DEFAULT_CHANNEL']
    response_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_check_all_album_urls.delay(response)
    return 'Check request sent', 200


@slack_blueprint.route('/process', methods=['POST'])
@admin_only
def process():
    form_data = flask.request.form
    default_channel = flask.current_app.config['DEFAULT_CHANNEL']
    response_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_process_all_album_details.delay(response)
    return 'Process request sent', 200


@slack_blueprint.route('/process/covers', methods=['POST'])
@admin_only
def process_covers():
    form_data = flask.request.form
    default_channel = flask.current_app.config['DEFAULT_CHANNEL']
    response_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_process_all_album_covers.delay(response)
    return 'Process request sent', 200


@slack_blueprint.route('/process/tags', methods=['POST'])
@admin_only
def process_tags():
    form_data = flask.request.form
    default_channel = flask.current_app.config['DEFAULT_CHANNEL']
    response_url = flask.current_app.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_process_all_album_tags.delay(response)
    return 'Process request sent', 200


@slack_blueprint.route('/link', methods=['POST'])
def link():
    form_data = flask.request.form
    album_id = form_data.get('text')
    if not album_id:
        return 'Provide an album ID', 401
    try:
        _, _, _, url, _, _, _, _ = flask.current_app.get_cached_album_details(album_id)
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return db_error_message, 500
    except TypeError as e:
        print(f'[slack]: no album found for link: {e}')
        return not_found_message, 404
    else:
        response = {
            'response_type': 'in_channel',
            'text': url,
            'unfurl_links': 'true',
        }
        return flask.jsonify(response), 200


@slack_blueprint.route('/random', methods=['POST'])
def random_album():
    form_data = flask.request.form
    try:
        _, _, _, url, img = albums_model.get_random_album()
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return db_error_message, 500
    except TypeError as e:
        print(f'[slack]: no album found for random: {e}')
        return not_found_message, 404
    else:
        response_type = 'in_channel' if 'post' in form_data.get('text', '') else 'ephemeral'
        response = {
            'response_type': response_type,
            'text': url,
            'unfurl_links': 'true',
        }
        return flask.jsonify(response), 200


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
            'footer': flask.current_app.config['LIST_NAME'],
        }
        attachments.append(attachment)

    return {
        'text': f'Your search returned {len(details)} results',
        'attachments': attachments,
    }


@slack_blueprint.route('/search', methods=['POST'])
def search():
    form_data = flask.request.form
    query = form_data.get('text')
    if query:
        response = flask.current_app.cache.get(f'q-{query}')
        if not response:
            func = functools.partial(albums_model.search_albums, query)
            try:
                details = build_album_details(func)
            except DatabaseError as e:
                print('[db]: failed to build album details')
                print(f'[db]: {e}')
                return 'failed to perform search', 500
            else:
                response = build_search_response(details)
                flask.current_app.cache.set(f'q-{query}', response, 60 * 15)
        return flask.jsonify(response), 200
    return '', 200


@slack_blueprint.route('/tags', methods=['POST'])
def search_tags():
    form_data = flask.request.form
    query = form_data.get('text')
    if query:
        response = flask.current_app.cache.get(f't-{query}')
        if not response:
            func = functools.partial(albums_model.search_albums_by_tag, query)
            try:
                details = build_album_details(func)
            except DatabaseError as e:
                print('[db]: failed to build album details')
                print(f'[db]: {e}')
                return 'failed to perform search', 500
            else:
                response = build_search_response(details)
                flask.current_app.cache.set(f't-{query}', response, 60 * 15)
        return flask.jsonify(response), 200
    return '', 200


@slack_blueprint.route('/search/button', methods=['POST'])
def button():
    try:
        form_data = json.loads(flask.request.form['payload'])
    except KeyError:
        print('[slack]: payload missing from button')
        return '', 401
    try:
        action = form_data['actions'][0]
        if 'tag' in action['name']:
            query = action['value']
            search_response = flask.current_app.cache.get(f't-{query}')
            if not search_response:
                func = functools.partial(albums_model.search_albums_by_tag, query)
                try:
                    details = build_album_details(func)
                except DatabaseError as e:
                    print('[db]: failed to build album details')
                    print(f'[db]: {e}')
                    return 'failed to perform search', 500
                else:
                    search_response = build_search_response(details)
                    flask.current_app.cache.set(f't-{query}', search_response, 60 * 15)
            response = {
                'response_type': 'ephemeral',
                'text': f'Your #{query} results',
                'replace_original': 'false',
                'unfurl_links': 'true',
                'attachments': search_response['attachments'],
            }
            return flask.jsonify(response)
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
            return flask.jsonify(response)
    except KeyError as e:
        print(f'[slack]: failed to build results: {e}')
        return db_error_message, 500
    return '', 200


@slack_blueprint.route('/auth', methods=['GET'])
def auth():
    code = flask.request.args.get('code')
    url = constants.SLACK_AUTH_URL.format(code=code, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
    response = requests.get(url)
    print(f'[auth]: {response.json()}')
    return response.content, 200
