import os

from albumlist.models import albums as albums_model
from albumlist.models import DatabaseError
import slacker


channel = os.environ.get('AOTD_CHANNEL_ID')
slack_token = os.environ.get('SLACK_OAUTH_TOKEN')
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
        message = f":new_moon_with_face: Today's album of the day is: {album.album_url}"
        print(f'[random]: posting random album to {channel}')
        slack.chat.post_message(channel, message, unfurl_links=True)


if __name__ == '__main__':
    post_random_album()
