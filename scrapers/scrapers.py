import requests
import json


class NotFoundError(Exception):
    pass


def scrape_links_from_attachments(messages):
    for message in messages:
        if message.get('type') == 'message':
            for attachment in message.get('attachments', []):
                try:
                    yield attachment['from_url']
                except KeyError:
                    continue


def scrape_links_from_text(messages):
    for message in messages:
        if message.get('type') == 'message':
            text = message.get('text', '')  
            try:
                if 'http' in text:
                    yield text
            except TypeError:
                pass


def scrape_bandcamp_album_ids_from_attachments(message):
    for attachment in message['attachments']:
        try:
            if 'bandcamp.com' in attachment['from_url']:
                html = attachment['audio_html']
                html.replace('\\', '')
                _, seg = html.split('album=')
                yield seg[:seg.find('/')]
        except (ValueError, KeyError):
            continue


def scrape_bandcamp_album_ids_from_url(url):
    comment = '<!-- album id '
    comment_len = len(comment)
    if 'http' in url and 'bandcamp.com' in url:
        url = url.replace('<', '').replace('>', '')
        url = url.replace('\\', '').split('|')[0]
        response = requests.get(url)
        if response.ok:
            content = response.text
            if comment in content:
                pos = content.find(comment)
                album_id = content[pos + comment_len:pos + comment_len + 20]
                return album_id.split('-->')[0].strip()
    raise NotFoundError


def scrape_bandcamp_album_ids_from_messages(messages, do_requests=True):
    for message in messages:
        if message.get('type') == 'message':
            if 'attachments' in message:
                for album_id in scrape_bandcamp_album_ids_from_attachments(message):
                    yield str(album_id)
            elif do_requests:
                try:
                    yield str(scrape_bandcamp_album_ids_from_url(message['text']))
                except (ValueError, KeyError, NotFoundError):
                    continue


def scrape_album_details_from_id(album_id):
    variable_text = 'var playerdata = '
    response = requests.get('https://bandcamp.com/EmbeddedPlayer/v=2/album=%s' % album_id)
    if response.ok:
        content = response.text
        player_data_pos = content.find(variable_text)
        if player_data_pos > 0:
            player_data_pos += len(variable_text)
            player_data_end_pos = player_data_pos + content[player_data_pos:].find('\n') - 1
            try:
                data = json.loads(content[player_data_pos:player_data_end_pos])
                return data['album_title'], data['artist'], data['linkback']
            except (KeyError, TypeError, ValueError):
                pass
    return None 

