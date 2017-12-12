import collections


def build_attachment(album_id, album_details, list_name, tags=True, scrape=False, delete=False):
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
    if scrape:
        attachment['callback_id'] = f'bandcamp_#{album_id}'
        attachment['actions'] += [
            {
                'name': 'scrape_album',
                'text': 'Scrape',
                'type': 'button',
                'value': album_details['url'],
            }
        ]
    if delete:
        attachment['actions'] = [
            {
                'name': 'delete_album',
                'text': 'Delete',
                'type': 'button',
                'value': album_id,
            }
        ]
    return attachment
