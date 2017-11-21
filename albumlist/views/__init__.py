import collections


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
