import functools
import json
import random
import re

import flask
import requests
import slacker

from albumlist import constants
from albumlist.delayed import queued
from albumlist.models import DatabaseError
from albumlist.models import albums as albums_model, list as list_model
from albumlist.scrapers import NotFoundError, bandcamp, links
from albumlist.views import build_attachment


slack_blueprint = flask.Blueprint(name='slack',
                                  import_name=__name__,
                                  url_prefix='/slack')


def slack_check(func):
    """
    Decorator for locking down slack endpoints to registered apps only
    """

    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if flask.request.form.get('token', '') in slack_blueprint.config['APP_TOKENS'] \
                or slack_blueprint.config['DEBUG']:
            return func(*args, **kwargs)
        flask.current_app.logger.error('[access]: failed slack-check test')
        flask.abort(403)

    return wraps


def admin_only(func):
    """
    Decorator for locking down slack endpoints to admins
    """

    @functools.wraps(func)
    def wraps(*args, **kwargs):
        if slack_blueprint.config['DEBUG']:
            return func(*args, **kwargs)
        slack_token = slack_blueprint.config['SLACK_OAUTH_TOKEN']
        if not slack_token:
            flask.abort(401)
        slack = slacker.Slacker(slack_token)
        user_id = flask.request.form['user_id']
        flask.current_app.logger.info(f'[access]: performing admin check...')
        try:
            info = slack.users.info(user_id)
        except slacker.Error:
            flask.current_app.logger.info(f'[access]: {user_id} not found')
            flask.abort(403)
        if info.body['user']['is_admin']:
            return func(*args, **kwargs)
        flask.current_app.logger.error('[access]: failed admin-only test')
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
        flask.current_app.logger.error('[access]: failed not-bot test')
        flask.abort(403)

    return wraps


@slack_blueprint.route('/admin/check', methods=['POST'])
@slack_check
@admin_only
def admin_check():
    return 'OK', 200


@slack_blueprint.route('/spoiler', methods=['POST'])
@slack_check
def spoiler():
    form_data = flask.request.form
    user = form_data['user_name']
    text = form_data['text']
    url = form_data['response_url']
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


@slack_blueprint.route('/scrape/urls', methods=['POST'])
@slack_check
@not_bots
def scrape_urls():
    form_data = flask.request.form
    channel = form_data.get('channel_name', 'chat')
    contents = form_data.get('text', '')
    for url in links.scrape_links_from_text(contents):
        queued.deferred_consume.delay(
            url,
            bandcamp.scrape_bandcamp_album_ids_from_url_forced,
            list_model.add_to_list,
            channel=channel,
            slack_token=slack_blueprint.config['SLACK_OAUTH_TOKEN']
        )
    return 'Scrape request sent', 200


@slack_blueprint.route('/scrape/artist', methods=['POST'])
@slack_check
@admin_only
def scrape_artist():
    form_data = flask.request.form
    contents = form_data.get('text', '')
    response = None if 'silence' in form_data else form_data.get('response_url')
    for url in links.scrape_links_from_text(contents):
        if 'bandcamp' in url:
            flask.current_app.logger.info(f'[scraper]: scraping albums from {url}')
            queued.deferred_consume_artist_albums.delay(url, response)
    return 'Scrape request sent', 200


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
    if album_id:
        response = None if 'silence' in form_data else form_data.get('response_url')
        queued.deferred_delete.delay(album_id.strip(), response)
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
            flask.current_app.logger.error('[db]: failed to add new album')
            flask.current_app.logger.error(f'[db]: {e}')
            return 'Failed to add new album', 200
        else:
            return 'Added new album', 200
    return '', 200


@slack_blueprint.route('/clear', methods=['POST'])
@slack_check
@admin_only
def clear_cache():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url')
    queued.deferred_clear_cache.delay(response)
    return 'Clear cache request sent', 200


@slack_blueprint.route('/scrape/channels', methods=['POST'])
@slack_check
@admin_only
def scrape():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url')
    contents = form_data.get('text', '')
    channels = re.findall(constants.SLACK_CHANNEL_REGEX, contents)
    slack_token = slack_blueprint.config['SLACK_OAUTH_TOKEN']
    if not slack_token:
        return 'Requires API scope', 200
    if channels:
        for channel_id, channel_name in channels:
            queued.deferred_scrape_channel.delay(
                bandcamp.scrape_bandcamp_album_ids_from_messages,
                list_model.add_many_to_list,
                channel_id,
                slack_token,
                channel_name=channel_name,
                response_url=response,
            )
            flask.current_app.logger.info(f'[slack]: scrape request sent for #{channel_name}')
    return 'Scrape request(s) sent', 200


@slack_blueprint.route('/process/check', methods=['POST'])
@slack_check
@admin_only
def check_urls():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url')
    queued.deferred_check_all_album_urls.delay(response)
    return 'Check all albums request sent...', 200


@slack_blueprint.route('/process/duplicates', methods=['POST'])
@slack_check
@admin_only
def check_for_duplicates():
    duplicates = albums_model.find_album_artist_duplicates()
    max_attachments = slack_blueprint.config['SLACK_MAX_ATTACHMENTS']
    list_name = slack_blueprint.config['LIST_NAME']
    response = build_search_response(duplicates, list_name, max_attachments, delete=True)
    return flask.jsonify(response), 200


@slack_blueprint.route('/process/unavailable', methods=['POST'])
@slack_check
@admin_only
def process_unavailable_albums():
    unavailable_albums = albums_model.get_albums_unavailable()
    max_attachments = slack_blueprint.config['SLACK_MAX_ATTACHMENTS']
    list_name = slack_blueprint.config['LIST_NAME']
    response = build_search_response(unavailable_albums, list_name, max_attachments, delete=True)
    return flask.jsonify(response), 200


@slack_blueprint.route('/process', methods=['POST'])
@slack_check
@admin_only
def process():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url')
    queued.deferred_process_all_album_details.delay(response)
    return 'Process request sent', 200


@slack_blueprint.route('/process/covers', methods=['POST'])
@slack_check
@admin_only
def process_covers():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url')
    queued.deferred_process_all_album_covers.delay(response)
    return 'Process request sent', 200


@slack_blueprint.route('/process/tags', methods=['POST'])
@slack_check
@admin_only
def process_tags():
    form_data = flask.request.form
    response = None if 'silence' in form_data else form_data.get('response_url')
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
        album = flask.current_app.get_cached_album_details(album_id)
        if album is None:
            return flask.current_app.not_found_message, 404
        response = {
            'response_type': 'in_channel',
            'text': album.album_url,
            'unfurl_links': True,
        }
        return flask.jsonify(response), 200
    except DatabaseError as e:
        flask.current_app.logger.error('[db]: failed to get album')
        flask.current_app.logger.error(f'[db]: {e}')
        return flask.current_app.db_error_message, 500


@slack_blueprint.route('/random', methods=['POST'])
@slack_check
def random_album():
    form_data = flask.request.form
    try:
        album = albums_model.get_random_album()
        if album is None:
            return flask.current_app.not_found_message, 404
    except DatabaseError as e:
        flask.current_app.logger.error('[db]: failed to get random album')
        flask.current_app.logger.error(f'[db]: {e}')
        return flask.current_app.db_error_message, 500
    else:
        if 'post' in form_data.get('text', ''):
            response = {
                'response_type': 'in_channel',
                'text': f'{album.album_url}',
                'unfurl_links': True
            }
        else:
            attachment = build_attachment(
                album.album_id,
                album.to_dict(),
                slack_blueprint.config['LIST_NAME'],
                tags=False,
            )
            response = {
                'response_type': 'ephemeral',
                'text': 'Your random album is...',
                'attachments': [attachment],
            }
        return flask.jsonify(response), 200


def build_search_response(albums, list_name, max_attachments=None, delete=False, add_to_my_list=False,
                          remove_from_my_list=False):
    details = albums_model.Album.details_map_from_albums(albums)
    attachments = [
        build_attachment(album_id, album_details, list_name,
                         add_to_my_list=add_to_my_list,
                         remove_from_my_list=remove_from_my_list,
                         delete=delete)
        for album_id, album_details in details.items()
    ]
    text = f'Your {list_name} search returned {len(details)} results'
    if max_attachments and len(details) > max_attachments:
        text += f' (but we can only show you {max_attachments})'
    return {
        'text': text,
        'attachments': attachments[:max_attachments],
    }


def build_bandcamp_search_response(album_details, max_attachments=None):
    album_map = {
        result_id: {
            'album': details[0],
            'artist': details[1],
            'url': details[2],
            'img': details[3],
            'tags': [],
        } for result_id, details in enumerate(album_details)
    }
    attachments = list(reversed([
        build_attachment(album_id, album_details, 'bandcamp', tags=False, scrape=True)
        for album_id, album_details in album_map.items()
    ]))
    text = f'Your bandcamp search returned {len(album_map)} results'
    if max_attachments and len(album_map) > max_attachments:
        text += f' (but we can only show you {max_attachments})'
    return {
        'text': text,
        'attachments': attachments[:max_attachments],
    }


@slack_blueprint.route('/search', methods=['POST'])
@slack_check
def search():
    form_data = flask.request.form
    query = form_data.get('text').lower()
    if query:
        response = flask.current_app.cache.get(f'q-{query}')
        if not response:
            try:
                albums = albums_model.search_albums(query)
            except DatabaseError as e:
                flask.current_app.logger.error('[db]: failed to build album details')
                flask.current_app.logger.error(f'[db]: {e}')
                return 'failed to perform search', 500
            else:
                max_attachments = slack_blueprint.config['SLACK_MAX_ATTACHMENTS']
                list_name = slack_blueprint.config['LIST_NAME']
                response = build_search_response(albums, list_name, max_attachments)
                flask.current_app.cache.set(f'q-{query}', response, 60 * 5)
        return flask.jsonify(response), 200
    return '', 200


@slack_blueprint.route('/search/bandcamp', methods=['POST'])
@slack_check
def search_bandcamp():
    form_data = flask.request.form
    query = form_data.get('text').lower()
    if query:
        response = flask.current_app.cache.get(f'bcq-{query}')
        if not response:
            try:
                max_attachments = slack_blueprint.config['SLACK_MAX_ATTACHMENTS']
                results = bandcamp.scrape_bandcamp_album_details_from_search(query)
                response = build_bandcamp_search_response(results, max_attachments)
                flask.current_app.cache.set(f'bcq-{query}', response, 60 * 5)
            except NotFoundError:
                return '', 404
        return flask.jsonify(response), 200
    return '', 200


@slack_blueprint.route('/tags', methods=['POST'])
@slack_check
def search_tags():
    form_data = flask.request.form
    query = form_data.get('text').lower()
    if query:
        response = flask.current_app.cache.get(f't-{query}')
        if not response:
            try:
                albums = albums_model.search_albums_by_tag(query)
            except DatabaseError as e:
                flask.current_app.logger.error('[db]: failed to build album details')
                flask.current_app.logger.error(f'[db]: {e}')
                return 'failed to perform search', 500
            else:
                max_attachments = slack_blueprint.config['SLACK_MAX_ATTACHMENTS']
                list_name = slack_blueprint.config['LIST_NAME']
                response = build_search_response(albums, list_name, max_attachments)
                flask.current_app.cache.set(f't-{query}', response, 60 * 15)
        return flask.jsonify(response), 200
    return '', 200


@slack_blueprint.route('/interactive', methods=['POST'])
def buttons():
    try:
        form_data = flask.request.form
        payload = json.loads(form_data['payload'])
    except KeyError:
        flask.current_app.logger.error('[slack]: payload missing from button')
        return '', 401
    if payload.get('token') not in slack_blueprint.config['APP_TOKENS']:
        flask.current_app.logger.error('[access]: button failed slack test')
        return '', 403
    try:
        return {
            'message_action': handle_message_action,
            'interactive_message': handle_interactive_message,
        }[payload['type']](payload)
    except KeyError as unknown_type:
        flask.current_app.logger.warn(f'[slack]: unknown message type: {unknown_type}')
    return '', 200


def handle_message_action(payload):
    try:
        if 'scrape_action' in payload['callback_id']:
            contents = payload['message']['text']
            channel_id = payload['channel']['id']
            for url in links.scrape_links_from_text(contents):
                queued.deferred_consume.delay(
                    url,
                    bandcamp.scrape_bandcamp_album_ids_from_url_forced,
                    list_model.add_to_list,
                    channel=channel_id,
                    slack_token=slack_blueprint.config['SLACK_OAUTH_TOKEN']
                )
            response = {
                'response_type': 'ephemeral',
                'text': f'Scraping message for albums to add to the {slack_blueprint.config["LIST_NAME"]}...',
                'replace_original': False,
                'unfurl_links': False,
            }
            requests.post(payload['response_url'], data=json.dumps(response))
        elif 'more_action' in payload['callback_id']:
            url = next(links.scrape_links_from_attachments([payload['message']]))
            album = albums_model.get_album_details_by_url(url)
            if album:
                random_tag_to_use = random.choice(album.tags)
                first_result = next(albums_model.search_albums_by_tag(random_tag_to_use))
                slack = slacker.Slacker(slack_blueprint.config['SLACK_OAUTH_TOKEN'])
                slack.chat.post_message(payload['user']['id'],
                                        f'Your requested similar album: {first_result.album_url}',
                                        unfurl_links=True)
            else:
                flask.current_app.logger.warn(f'[slack]: unable to find album by url: {url}')
        elif 'add_mine' in payload['callback_id']:
            url = next(links.scrape_links_from_attachments([payload['message']]))
            album = albums_model.get_album_details_by_url(url)
            if album:
                albums_model.add_user_to_album(album.album_id, payload['user']['id'])
                flask.current_app.logger.info(f'[slack]: added user to album')
                response = {
                    'response_type': 'ephemeral',
                    'text': f'Added album to your list. Use `/my_albums` to see all...',
                    'replace_original': False,
                    'unfurl_links': False,
                }
                requests.post(payload['response_url'], data=json.dumps(response))
            else:
                flask.current_app.logger.warn(f'[slack]: unable to find album by url: {url}')
    except StopIteration:
        flask.current_app.logger.warn(f'[slack]: no URL found in message')
    except KeyError as missing_key:
        flask.current_app.logger.warn(f'[slack]: missing key in action payload: {missing_key}')
    return '', 200


def handle_interactive_message(payload):
    try:
        action = payload['actions'][0]
        if 'tag' in action['name']:
            query = action['value'].lower()
            search_response = flask.current_app.cache.get(f't-{query}')
            if not search_response:
                try:
                    albums = albums_model.search_albums_by_tag(query)
                except DatabaseError as e:
                    flask.current_app.logger.error('[db]: failed to build album details')
                    flask.current_app.logger.error(f'[db]: {e}')
                    return 'failed to perform search', 500
                else:
                    max_attachments = slack_blueprint.config['SLACK_MAX_ATTACHMENTS']
                    list_name = slack_blueprint.config['LIST_NAME']
                    search_response = build_search_response(albums, list_name, max_attachments)
                    flask.current_app.cache.set(f't-{query}', search_response, 60 * 5)
            response = {
                'response_type': 'ephemeral',
                'text': f'Your #{query} results',
                'replace_original': False,
                'unfurl_links': True,
                'attachments': search_response['attachments'],
            }
            return flask.jsonify(response)
        elif 'post_album' in action['name']:
            url = action['value']
            user = payload['user']['name']
            if payload['callback_id'].startswith('bandcamp_#'):
                message = f'{user} posted {url} from bandcamp search results'
            else:
                message = f"{user} posted {url} from the {slack_blueprint.config['LIST_NAME']}"
            response = {
                'response_type': 'in_channel',
                'text': message,
                'replace_original': False,
                'unfurl_links': True,
            }
            return flask.jsonify(response)
        elif 'scrape_album' in action['name']:
            url = action['value']
            channel_id = payload['channel']['id']
            queued.deferred_consume.delay(
                url,
                bandcamp.scrape_bandcamp_album_ids_from_url,
                list_model.add_to_list,
                channel=channel_id,
                slack_token=slack_blueprint.config['SLACK_OAUTH_TOKEN']
            )
            response = {
                'response_type': 'ephemeral',
                'text': f'Scraping from {url}...',
                'replace_original': False,
                'unfurl_links': False,
            }
            return flask.jsonify(response)
        elif 'delete_album' in action['name']:
            queued.deferred_delete.delay(action['value'], response_url=payload.get('response_url'))
            response = {
                'response_type': 'ephemeral',
                'text': 'Deleting...',
                'replace_original': False,
                'unfurl_links': False,
            }
            return flask.jsonify(response)
        elif 'add_to_my_list' in action['name']:
            queued.deferred_add_user_to_album.delay(action['value'], payload['user']['id'],
                                                    response_url=payload.get('response_url'))
            return '', 200
        elif 'remove_from_my_list' in action['name']:
            queued.deferred_remove_user_from_album.delay(action['value'], payload['user']['id'],
                                                         response_url=payload.get('response_url'))
            response = {
                'response_type': 'ephemeral',
                'text': f'Removing...',
                'replace_original': False,
                'unfurl_links': False,
            }
            return flask.jsonify(response)
    except KeyError as missing_key:
        flask.current_app.logger.warn(f'[slack]: missing key in interactive payload: {missing_key}')
    return '', 200


@slack_blueprint.route('/restore_from_url', methods=['POST'])
@slack_check
@admin_only
def restore_albums():
    contents = flask.request.form.get('text', '')
    try:
        url = links.scrape_links_from_text(contents)[0]
        queued.deferred_fetch_and_restore.delay(url)
    except IndexError:
        flask.abort(401)
    return 'Restore request sent...', 200


@slack_blueprint.route('/my_albums', methods=['POST'])
@slack_check
def my_albums():
    user = flask.request.form.get('user_id')
    if user:
        response = flask.current_app.cache.get(f'u-{user}')
        if not response:
            try:
                albums = albums_model.get_albums_by_user(user)
            except DatabaseError as e:
                flask.current_app.logger.error('[db]: failed to build album details')
                flask.current_app.logger.error(f'[db]: {e}')
                return 'failed to perform search', 500
            else:
                max_attachments = slack_blueprint.config['SLACK_MAX_ATTACHMENTS']
                response = build_search_response(albums, 'My List', max_attachments,
                                                 add_to_my_list=False,
                                                 remove_from_my_list=True)
                flask.current_app.cache.set(f'u-{user}', response, 5)
        return flask.jsonify(response), 200
    return '', 200


@slack_blueprint.route('/events', methods=['POST'])
def events_handler():
    if int(flask.request.headers.get('X-Slack-Retry-Num', 0)) > 1:
        return '', 200

    body = flask.request.json
    token = body.get('token', '')

    if token in slack_blueprint.config['APP_TOKENS'] or slack_blueprint.config['DEBUG']:
        try:
            request_type = body['type']

            if request_type == 'event_callback':
                event_type = body['event']['type']

                if event_type == 'link_shared':
                    channel = body['event']['channel']

                    for event_link in body['event']['links']:
                        flask.current_app.logger.info(f"[events]: link shared matching {event_link['domain']}")
                        queued.deferred_consume.delay(
                            event_link['url'],
                            bandcamp.scrape_bandcamp_album_ids_from_url,
                            list_model.add_to_list,
                            channel=channel,
                            slack_token=slack_blueprint.config['SLACK_OAUTH_TOKEN']
                        )

        except KeyError:
            flask.abort(401)
    else:
        flask.current_app.logger.error('[events]: failed slack-check test')
        flask.abort(403)
    return '', 200
