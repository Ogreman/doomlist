import ast
import csv
import io
import json

import flask
import requests
import slacker

from albumlist import delayed
from albumlist.models import DatabaseError
from albumlist.models import albums as albums_model, list as list_model
from albumlist.scrapers import NotFoundError
from albumlist.scrapers import bandcamp


@delayed.queue_func
def deferred_scrape_channel(scrape_function, callback, channel_id, slack_token, channel_name=None, response_url=None):
    try:
        slack = slacker.Slacker(slack_token)
        if response_url:
            requests.post(response_url, data=json.dumps({'text': f'Getting channel history for {channel_name or channel_id}...'}))
        response = slack.channels.history(channel_id)
    except (KeyError, slacker.Error) as e:
        message = 'There was an error accessing the Slack API'
        if response_url:
            requests.post(response_url, data=json.dumps({'text': message}))
        raise e
    if response.successful:
        messages = response.body.get('messages', [])
        if response_url:
            requests.post(response_url, data=json.dumps({'text': f'Scraping {channel_name or channel_id}...'}))
        album_ids = scrape_function(messages)
        new_album_ids = list_model.check_for_new_list_ids(album_ids)
        try:
            if new_album_ids:
                callback(new_album_ids)
                print(f'[scraper]: {len(new_album_ids)} new albums found and added to the list')
                deferred_process_all_album_details.delay(None)
        except DatabaseError as e:
            message = 'failed to update list'
            print(f'[db]: failed to perform {callback.__name__}')
            print(f'[db]: {e}')
        else:
            message = f'Finished checking for new albums: {len(new_album_ids)} found in {channel_name or channel_id}'
    else:
        message = f'failed to get channel history for {channel_name or channel_id}'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_consume(url, scrape_function, callback, channel='', tags=None, slack_token=None, response_url=None):
    try:
        album_id = scrape_function(url)
    except NotFoundError:
        print(f'[scraper]: no album id found at {url}')
    else:
        if slack_token:
            slack = slacker.Slacker(slack_token)
        try:
            if album_id not in list_model.get_list():
                try:    
                    callback(album_id)
                except DatabaseError as e:
                    print(f'[db]: failed to perform {callback.__name__}')
                    print(f'[db]: {e}')
                    if response_url:
                        requests.post(response_url, data=json.dumps({'text': ':red_circle: failed to update list'}))
                    elif slack_token and channel:
                        slack.chat.post_message(f'{channel}', ':red_circle: failed to update list')
                else:
                    if response_url:
                        requests.post(response_url, data=json.dumps({'text': f':full_moon: added album to list: {url}', 'unfurl_links': True}))
                    elif slack_token and channel:
                        slack.chat.post_message(f'{channel}', f':full_moon: added album to list: {url}', unfurl_links=True)
                    deferred_process_album_details.delay(str(album_id), channel, slack_token)
            elif response_url:
                requests.post(response_url, data=json.dumps({'text': f':new_moon: album already in list: {url}', 'unfurl_links': True}))
            elif slack_token and channel:
                slack.chat.post_message(f'{channel}', f':new_moon: album already in list: {url}', unfurl_links=True)
            if tags:
                deferred_process_tags.delay(str(album_id), tags)
        except DatabaseError as e:
            print('[db]: failed to check existing items')
            print(f'[db]: {e}')


@delayed.queue_func
def deferred_consume_artist_albums(artist_url, response_url=None):
    try:
        existing_albums = list_model.get_list()
        artist_albums = bandcamp.scrape_bandcamp_album_ids_from_artist_page(artist_url)
        new_album_ids = [album_id for album_id in artist_albums if album_id not in existing_albums]
        if response_url and new_album_ids:
            requests.post(response_url, data=json.dumps({'text': f':full_moon: found {len(new_album_ids)} new albums to process...'}))
        elif response_url:
            requests.post(response_url, data=json.dumps({'text': f':new_moon: found no new albums to process'}))
    except DatabaseError as e:
        print('[db]: failed to check existing items')
        print(f'[db]: {e}')
    except NotFoundError:
        print(f'[scraper]: no albums found for artist at {artist_url}')
        if response_url:
            requests.post(response_url, data=json.dumps({'text': ':red_circle: failed to find any albums'}))
    else:
        for new_album_id in new_album_ids:
            try:
                list_model.add_to_list(new_album_id)
                deferred_process_album_details.delay(str(new_album_id))
            except DatabaseError as e:
                print(f'[db]: failed to update list with {new_album_id} from {artist_url}')
                print(f'[db]: {e}')
        if response_url and new_album_ids:
            requests.post(response_url, data=json.dumps({'text': f':full_moon_with_face: done processing artist albums'}))


@delayed.queue_func
def deferred_process_tags(album_id, tags):
    tags = [tag[1:].lower() if tag.startswith('#') else tag.lower() for tag in tags]
    try:
        albums_model.set_album_tags(album_id, tags)
    except DatabaseError as e:
        print(f'[db]: failed to add tags "{tags}" to album {album_id}')
        print(f'[db]: {e}')
    else:
        print(f'[scraper]: tagged {album_id} with "{tags}"')


@delayed.queue_func
def deferred_process_all_album_details(response_url=None):
    try:
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Process started...'}))
        for album_id in albums_model.check_for_new_albums():
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
def deferred_clear_cache(response_url=None):
    flask.current_app.cache.clear()
    if response_url:
        requests.post(response_url, data=json.dumps({'text': 'Cache cleared'}))


@delayed.queue_func
def deferred_delete(album_id, response_url=None):
    try:
        albums_model.delete_from_list_and_albums(album_id)
        flask.current_app.cache.delete(f'alb-{album_id}')
    except DatabaseError as e:
        print(f'[db]: failed to delete album details for {album_id}')
        print(f'[db]: {e}')
        message = f'failed to delete album details for {album_id}'
    else:
        print(f'[db]: deleted album details for {album_id}')
        message = f'Removed album from list: {album_id}'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_add_user_to_album(album_url, user_id, response_url=None):
    try:
        album = albums_model.get_album_details_by_url(album_url)
        if album:
            albums_model.add_user_to_album(album.album_id, user_id)
        else:
            deferred_consume.delay(
                album_url,
                bandcamp.scrape_bandcamp_album_ids_from_url_forced,
                list_model.add_to_list,
                response_url=response_url,
            )
            deferred_add_user_to_album.delay(album_url, user_id, response_url=response_url)
            return
        flask.current_app.cache.delete(f'u-{user_id}')
    except DatabaseError as e:
        print(f'[db]: failed to add user to album')
        print(f'[db]: {e}')
        message = f'failed to add album to user\'s list'
    else:
        print(f'[db]: added user to album')
        message = f'Added album to your list. Use `/my_albums` to see all...'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_remove_user_from_album(album_id, user_id, response_url=None):
    try:
        albums_model.remove_user_from_album(album_id, user_id)
        flask.current_app.cache.delete(f'u-{user_id}')
    except DatabaseError as e:
        print(f'[db]: failed to remove user from album')
        print(f'[db]: {e}')
        message = f'failed to remove album from user\'s list'
    else:
        print(f'[db]: removed user from album')
        message = f'Removed album from your list.'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_process_album_details(album_id, channel='', slack_token=None):
    try:
        album, artist, url = bandcamp.scrape_bandcamp_album_details_from_id(album_id)
        albums_model.add_to_albums(album_id, artist, album, url, channel=channel)
        deferred_process_album_cover.delay(album_id)
        deferred_process_album_tags.delay(album_id)
    except DatabaseError as e:
        print(f'[db]: failed to add album details for {album_id}')
        print(f'[db]: {e}')
        if channel and slack_token:
            slacker.Slacker(slack_token).chat.post_message(f'{channel}', f':red_circle: failed to add album details')
    except (TypeError, ValueError):
        pass
    else:
        print(f'[scraper]: processed album details for {album_id}')
        if channel and slack_token:
            slacker.Slacker(slack_token).chat.post_message(f'{channel}', f':full_moon_with_face: processed album details for "*{album}*" by *{artist}*')
            deferred_attribute_album_url.delay(album_id, slack_token)


@delayed.queue_func
def deferred_add_new_album_details(album_id, added, album, artist, channel, img, tags, url):
    try:
        if album_id not in list_model.get_list():
            list_model.add_to_list(album_id)
        albums_model.add_to_albums(album_id, artist=artist, name=album, url=url, img=img, channel=channel)
        if added:
            albums_model.update_album_added(album_id, added)
        if not img:
            deferred_process_album_cover.delay(album_id)
        if tags is not None:
            if isinstance(tags, str):
                tags = ast.literal_eval(tags)
            deferred_process_tags.delay(album_id, tags)
        else:
            deferred_process_album_tags.delay(album_id)
        deferred_check_album_url.delay(album_id)
    except DatabaseError as e:
        print(f'[db]: failed to add new album details for [{album_id}] {album} by {artist}')
        print(f'[db]: {e}')
    else:
        print(f'[db]: added new album details for [{album_id}] {album} by {artist}')


@delayed.queue_func
def deferred_process_album_cover(album_id):
    try:
        album = albums_model.get_album_details(album_id)
        album_cover_url = bandcamp.scrape_bandcamp_album_cover_url_from_url(album.album_url)
        albums_model.add_img_to_album(album_id, album_cover_url)
    except DatabaseError as e:
        print(f'[db]: failed to add album cover for {album_id}')
        print(f'[db]: {e}')
    except NotFoundError as e:
        print(f'[scraper]: failed to find album art for {album_id}')
        print(f'[scraper]: {e}')
    except (TypeError, ValueError):
        pass
    else:
        print(f'[scraper]: processed cover for {album_id}')


@delayed.queue_func
def deferred_process_album_tags(album_id):
    try:
        album = albums_model.get_album_details(album_id)
        tags = bandcamp.scrape_bandcamp_tags_from_url(album.album_url)
        if tags:
            deferred_process_tags.delay(album_id, tags)
    except DatabaseError as e:
        print(f'[db]: failed to get album details for {album_id}')
        print(f'[db]: {e}')
    except (TypeError, ValueError):
        pass
    else:
        print(f'[scraper]: processed tags for {album_id}')


@delayed.queue_func
def deferred_process_all_album_covers(response_url=None):
    try:
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Process started...'}))
        for album in albums_model.get_albums_without_covers():
            deferred_process_album_cover.delay(album.album_id)
    except DatabaseError as e:
        print('[db]: failed to get all album details')
        print(f'[db]: {e}')
        message = 'failed to process all album details...'
    else:
        message = 'Processed all album covers'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_process_all_album_tags(response_url=None):
    try:
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Process started...'}))
        for album in albums_model.get_albums():
            deferred_process_album_tags.delay(album.album_id)
    except DatabaseError as e:
        print('[db]: failed to get all album details')
        print(f'[db]: {e}')
        message = 'failed to process all album details...'
    else:
        message = 'Processed all album tags'
    if response_url:
        requests.post(response_url, data=json.dumps({'text': message}))


@delayed.queue_func
def deferred_check_album_url(album_id, check_for_new_url=True):
    try:
        album = albums_model.get_album_details(album_id)
        response = requests.head(album.album_url)
        if response.ok and not album.available:
            print(f'[scraper]: [{album_id}] {album.album_name} by {album.album_artist} is now available')
            albums_model.update_album_availability(album_id, True)

        elif response.status_code > 400:

            if check_for_new_url:
                try:
                    _, _, album_url = bandcamp.scrape_bandcamp_album_details_from_id(album_id)
                    if album_url != album.album_url:
                        print(f'[scraper] alternative album URL found at {album_url} for {album_id}')
                        albums_model.update_album_url(album_id, album_url)
                        return
                except TypeError:
                    print(f'[scraper] no alternative URL found for {album_id}')
                except DatabaseError as e:
                    print(f'[db]: failed to update album URL for {album_id}')
                    print(f'[db]: {e}')

            if album.available:
                albums_model.update_album_availability(album_id, False)
                message = f'[{album_id}] {album.album_name} by {album.album_artist} is no longer available'
                print(f'[scraper]: {message}')

    except DatabaseError as e:
        print('[db]: failed to update album after check')
        print(f'[db]: {e}')
    except (TypeError, ValueError):
        pass
    else:
        print(f'[scraper]: checked availability for {album_id}')


@delayed.queue_func
def deferred_check_all_album_urls(response_url=None):
    try:
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Check started...'}))
        for album_id in albums_model.get_album_ids():
            deferred_check_album_url.delay(album_id)
    except DatabaseError as e:
        print('[db]: failed to check for new album details')
        print(f'[db]: {e}')
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'failed to check all album urls'}))


@delayed.queue_func
def deferred_attribute_album_url(album_id, slack_token):
    try:
        album = albums_model.get_album_details(album_id)
        album_url = album.album_url
        slack = slacker.Slacker(slack_token)
        response = slack.search.all(album_url)
        if response.successful:
            for match in response.body['messages']['matches']:
                user = match['user']
                if user:
                    albums_model.add_user_to_album(album_id, user)
                    print(f'[scraper]: added {user} to {album_id}')
                elif 'previous' in match and album_url in match['previous']['text']:
                    albums_model.add_user_to_album(album_id, match['previous']['user'])
                    print(f'[scraper]: added {match["previous"]["user"]} to {album_id}')
                elif 'previous2' in match and album_url in match['previous2']['text']:
                    albums_model.add_user_to_album(album_id, match['previous2']['user'])
                    print(f'[scraper]: added {match["previous2"]["user"]} to {album_id}')
    except (DatabaseError, KeyError) as e:
        print('[db]: failed to attribute users to album')
        print(f'[db]: {e}')


@delayed.queue_func
def deferred_attribute_users_to_all_album_urls(slack_token, response_url=None):
    try:
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'Attribution started...'}))
        for album_id in albums_model.get_album_ids():
            deferred_attribute_album_url.delay(album_id, slack_token)
    except DatabaseError as e:
        print('[db]: failed to start attribution process')
        print(f'[db]: {e}')
        if response_url:
            requests.post(response_url, data=json.dumps({'text': 'failed to check all album urls'}))


@delayed.queue_func
def deferred_ping_albumlistbot():
    slack_token = flask.current_app.config['SLACK_OAUTH_TOKEN']
    albumlistbot_url = flask.current_app.config['ALBUMLISTBOT_URL']
    print('[ping]: pinging albumlist bot...')
    response = requests.get(albumlistbot_url, params={'token': slack_token})
    if response.ok:
        print('[ping]: done')
    else:
        print(f'[ping]: unable to reach albumlist bot: {response.status_code}')


@delayed.queue_func
def deferred_fetch_and_restore(url_to_csv):
    response = requests.get(url_to_csv)
    if response.ok and csv.Sniffer().has_header(response.text):
        f = io.StringIO(response.text)
        reader = csv.reader(f)
        _ = next(reader)  # skip header
        for album_details in reader:
            deferred_add_new_album_details.delay(*tuple(album_details))
    else:
        print('[restore]: failed to get csv')
