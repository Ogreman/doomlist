import requests


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


def scrape_bandcamp_album_ids_from_urls(message):
    comment = '<!-- album id '
    comment_len = len(comment)
    text = message['text']
    if 'http' in text and 'bandcamp.com' in text and 'album' in text:
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


def scrape_bandcamp_album_ids(messages, do_requests=True):
    for message in messages:
        if message.get('type') == 'message':
            if 'attachments' in message:
                for album_id in scrape_bandcamp_album_ids_from_attachments(message):
                    yield str(album_id)
            elif do_requests:
                try:
                    yield str(scrape_bandcamp_album_ids_from_urls(message))
                except (ValueError, KeyError, NotFoundError):
                    continue


