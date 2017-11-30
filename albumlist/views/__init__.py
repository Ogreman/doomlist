import collections


def build_attachment(album_id, album_details, list_name, tags=True):
    attachment = {
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
                'name': 'post_album',
                'text': 'Post',
                'type': 'button',
                'value': album_details['url'],
            }
        ],
        'footer': list_name,
    }
    if tags:
        attachment['actions'] += [
            {
                'name': 'tag',
                'text': f'#{tag}',
                'type': 'button',
                'value': str(tag),
            }
            for i, tag in enumerate(album_details['tags'])
        ]
    return attachment
