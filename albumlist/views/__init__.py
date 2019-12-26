def get_embedded_url(album_id):
    return f'https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/bgcol=000000'


def build_attachment(album_id, album_details, list_name, add_to_my_list=True, remove_from_my_list=False, tags=True,
                     scrape=False, delete=False, preview_album=False):
    from datetime import datetime  # noqa

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
                'short': 'true',
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
    if album_details['released']:
        attachment['fields'].insert(
            1, {
                'title': 'Released',
                'value': datetime.strptime(album_details['released'], '%Y%m%d').strftime('%d %B %Y'),
                'short': 'true',
            }
        )
    if album_details['reviews']:
        attachment['fields'].insert(
            1, {
                'title': 'Reviewed',
                'value': f"{len(album_details['reviews'])} time{'s' if len(album_details['reviews']) > 1 else ''}",
                'short': 'true',
            }
        )
        attachment['actions'] += [
            {
                'name': 'list_reviews',
                'text': 'Reviews',
                'type': 'button',
                'value': album_id,

            }
        ]
    if preview_album:
        attachment['actions'] += [
            {
                'name': 'preview_album',
                'text': 'Preview',
                'type': 'button',
                'url': get_embedded_url(album_id),
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


def build_slack_modal(trigger_id):
    return {
        "trigger_id": trigger_id,
        "view": {
            "type": "modal",
            "callback_id": "review-modal",
            "title": {
                "type": "plain_text",
                "text": "Reviews"
            },
            "blocks": [{
                "type": "input",
                "block_id": "review-block",
                "label": {
                    "type": "plain_text",
                    "text": "Add your review"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "review-input",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter some plain text"
                    }
                }
            }],
        }
    }
