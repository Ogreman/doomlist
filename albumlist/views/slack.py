import flask
import functools
import json
import re
import requests
import slacker

from albumlist import constants
from albumlist.delayed import queued
from albumlist.models import DatabaseError
from albumlist.models import albums as albums_model, tags as tags_model, list as list_model
from albumlist.scrapers import bandcamp, links
from albumlist.views import build_album_details


slack_blueprint = flask.Blueprint(name='slack',
                               import_name=__name__,
                               url_prefix='/slack')


def slack_check(func):
    """
    Decorator for locking down slack endpoints to registered apps only
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if flask.request.form.get('token', '') in slack_blueprint.config['APP_TOKENS'] or slack_blueprint.config['DEBUG']:
            return func(*args, **kwargs)
        print('[access]: failed slack-check test')
        flask.abort(403)
    return wraps


def admin_only(func):
    """
    Decorator for locking down slack endpoints to admins
    """
    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if flask.request.form.get('user_id', '') in slack_blueprint.config['ADMIN_IDS'] or slack_blueprint.config['DEBUG']:
            return func(*args, **kwargs)
        print('[access]: failed admin-only test')
        flask.abort(403)
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
        flask.abort(403)
    return wraps


@slack_blueprint.route('/spoiler', methods=['POST'])
@slack_check
def spoiler():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    user = form_data['user_name']
    text = form_data['text']
    bot_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=channel)
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
@slack_check
@not_bots
def consume():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    bot_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=channel)
    queued.deferred_consume.delay(
        form_data.get('text', ''),
        bandcamp.scrape_bandcamp_album_ids_from_url,
        list_model.add_to_list,
        response_url=bot_url,
        channel=channel
    )
    return '', 200


@slack_blueprint.route('/consume/all', methods=['POST'])
@slack_check
def consume_all():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    bot_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=channel)
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
@slack_check
def album_count():
    return str(albums_model.get_albums_count()), 200


@slack_blueprint.route('/delete', methods=['POST'])
@slack_check
@admin_only
def delete():
    form_data = flask.request.form
    album_id = form_data.get('text')
    channel = form_data.get('channel_name', 'chat')
    if album_id:
        bot_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=channel)
        queued.deferred_delete.delay(album_id.strip(), bot_url)
    return '', 200


@slack_blueprint.route('/add', methods=['POST'])
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


@slack_blueprint.route('/clear', methods=['POST'])
@slack_check
@admin_only
def clear_cache():
    form_data = flask.request.form
    default_channel = slack_blueprint.config['DEFAULT_CHANNEL']
    response_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_clear_cache.delay(response)
    return 'Clear cache request sent', 200


@slack_blueprint.route('/scrape', methods=['POST'])
@slack_check
@admin_only
def scrape():
    form_data = flask.request.form
    default_channel = slack_blueprint.config['DEFAULT_CHANNEL']
    response_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    contents = form_data.get('text', '')
    channels = re.findall(constants.SLACK_CHANNEL_REGEX, contents)
    if channels:
        for channel_id, channel_name in channels:
            queued.deferred_scrape.delay(
                bandcamp.scrape_bandcamp_album_ids_from_messages,
                list_model.add_many_to_list,
                channel_id,
                channel_name,
                response
            )
            print(f'[slack]: scrape request sent for #{channel_name}')
    else:
        queued.deferred_scrape.delay(
            bandcamp.scrape_bandcamp_album_ids_from_messages,
            list_model.add_many_to_list,
            flask.current_app.config['SCRAPE_CHANNEL_ID'],
            response_url=response
        )
        print('[slack]: scrape request sent for default channel')
    return 'Scrape request(s) sent', 200


@slack_blueprint.route('/check', methods=['POST'])
@slack_check
@admin_only
def check_urls():
    form_data = flask.request.form
    default_channel = slack_blueprint.config['DEFAULT_CHANNEL']
    response_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_check_all_album_urls.delay(response)
    return 'Check request sent', 200


@slack_blueprint.route('/process', methods=['POST'])
@slack_check
@admin_only
def process():
    form_data = flask.request.form
    default_channel = slack_blueprint.config['DEFAULT_CHANNEL']
    response_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_process_all_album_details.delay(response)
    return 'Process request sent', 200


@slack_blueprint.route('/process/covers', methods=['POST'])
@slack_check
@admin_only
def process_covers():
    form_data = flask.request.form
    default_channel = slack_blueprint.config['DEFAULT_CHANNEL']
    response_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_process_all_album_covers.delay(response)
    return 'Process request sent', 200


@slack_blueprint.route('/process/tags', methods=['POST'])
@slack_check
@admin_only
def process_tags():
    form_data = flask.request.form
    default_channel = slack_blueprint.config['DEFAULT_CHANNEL']
    response_url = slack_blueprint.config['BOT_URL_TEMPLATE'].format(channel=default_channel)
    response = None if 'silence' in form_data else form_data.get('response_url', response_url)
    queued.deferred_process_all_album_tags.delay(response)
    return 'Process request sent', 200


@slack_blueprint.route('/link', methods=['POST'])
@slack_check
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
@slack_check
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
            'footer': slack_blueprint.config['LIST_NAME'],
        }
        attachments.append(attachment)

    max_attachments = slack_blueprint.config['SLACK_MAX_ATTACHMENTS']
    text = f'Your search returned {len(details)} results'
    if len(details) > max_attachments:
        text += f' (but we can only show you {max_attachments})'

    return {
        'text': text,
        'attachments': attachments[:max_attachments],
    }


@slack_blueprint.route('/search', methods=['POST'])
@slack_check
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
                flask.current_app.cache.set(f'q-{query}', response, 60 * 5)
        return flask.jsonify(response), 200
    return '', 200


@slack_blueprint.route('/tags', methods=['POST'])
@slack_check
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
    if form_data.get('token') not in slack_blueprint.config['APP_TOKENS']:
        print('[access]: button failed slack test')
        return '', 403
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
                    flask.current_app.cache.set(f't-{query}', search_response, 60 * 5)
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
@slack_check
def auth():
    code = flask.request.args.get('code')
    client_id = slack_blueprint.config['SLACK_CLIENT_ID']
    client_secret = slack_blueprint.config['SLACK_CLIENT_SECRET']
    url = constants.SLACK_AUTH_URL.format(code=code, client_id=client_id, client_secret=client_secret)
    response = requests.get(url)
    print(f'[auth]: {response.json()}')
    return response.content, 200
