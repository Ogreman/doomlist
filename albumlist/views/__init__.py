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
    for album_id, album, artist, url, img, _, channel, added, tag in func():
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


def build_attachment(album_id, album_details, list_name):
    tag_actions = [
        {
            'name': 'tag',
            'text': f'#{tag}',
            'type': 'button',
            'value': str(tag),
        }
        for i, tag in enumerate(album_details['tags'])
    ]
    return {
        'fallback': f'{album_details["album"]} by {album_details["artist"]}',
        'color': '#36a64f',
        'pretext': f'{album_details["album"]} by {album_details["artist"]}',
        'author_name': album_details['artist'],
        'image_url': album_details['img'],
        'title': album_details['album'],
        'title_link': album_details['url'],
        'callback_id': f'album_results_{album_id}',
        'fields': [
            {
                'title': 'Album ID',
                'value': album_id,
                'short': 'false',
            },
            {
                    'title': 'Tags',
                    'value': ', '.join(album_details['tags']),
                    'short': 'false',
            },
        ],
        'actions': [
            {
                'name': 'album',
                'text': 'Post',
                'type': 'button',
                'value': album_details['url'],
            }
        ] + tag_actions,
        'footer': list_name,
    }
