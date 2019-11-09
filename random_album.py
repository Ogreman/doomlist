import os

from albumlist.models import albums as albums_model
from albumlist.models import DatabaseError
from albumlist.views import build_attachment
import slacker


channel = os.environ.get('AOTD_CHANNEL_ID')
slack_token = os.environ.get('SLACK_OAUTH_TOKEN')
list_name = os.environ.get('LIST_NAME', 'Albumlist')
slack = slacker.Slacker(slack_token)


def post_random_album():
    if not channel or not slack_token:
        print('[random]: missing environment variables')
        return
    try:
        album = albums_model.get_random_album()
        if album is None:
            print('[random]: no random album found')
            return
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return
    else:
        attachment = build_attachment(
            album.album_id,
            album.to_dict(),
            list_name,
            preview_album=True,
            tags=True,
        )
        print(f'[random]: posting random album to {channel}')
        text = f":new_moon_with_face: Today's album of the day is:"
        slack.chat.post_message(channel, text, attachments=[attachment])


if __name__ == '__main__':
    post_random_album()
