def get_embedded_url(album_id):
    return f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=000000'


def build_attachment(album_id, album_details, list_name, add_to_my_list=True, remove_from_my_list=False, tags=True,
                     scrape=False, delete=False, preview_album=False):
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
                'value': get_embedded_url(album_id),
            }
        ],
        'footer': list_name,
    }
    if preview_album:
        attachment['actions'] += [
            {
                'name': 'preview_album',
                'text': 'Preview',
                'type': 'button',
                'url': album_details['url'],
            }
        ]
    if add_to_my_list:
        attachment['actions'] += [
            {
                'name': 'add_to_my_list',
                'text': 'Add to My List',
                'type': 'button',
                'value': album_details['url'],
            }
        ]
    elif remove_from_my_list:
        attachment['actions'] += [
            {
                'name': 'remove_from_my_list',
                'text': 'Remove from My List',
                'type': 'button',
                'value': album_id,
            }
        ]
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


def build_my_list_attachment():
    return [
        {
            "text": "My List",
            "fallback": "My List actions are not accessible",
            "callback_id": "my_list_action",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    'name': 'view_my_list',
                    'text': 'View',
                    'type': 'button',
                },
                {
                    'name': 'clear_my_list',
                    'style': 'danger',
                    'text': 'Clear',
                    'type': 'button',
                    'confirm': {
                        "title": "Are you sure?",
                        "text": "This will clear My List",
                        "ok_text": "Yes",
                        "dismiss_text": "No"
                    }
                }
            ]
        }
    ]
