import os

from albumlist.models import albums as albums_model
from albumlist.models import DatabaseError
from apscheduler.schedulers.blocking import BlockingScheduler
import slacker


channel = os.environ.get('AOTD_CHANNEL_ID')
hour = int(os.environ.get('AOTD_HOUR', 10))
sched = BlockingScheduler()
slack_token = os.environ.get('SLACK_OAUTH_TOKEN')
slack = slacker.Slacker(slack_token)


@sched.scheduled_job('cron', day_of_week='mon-fri', hour=hour)
def scheduled_job():
    if not enabled or not channel:
        return
    try:
        album = albums_model.get_random_album()
        if album is None:
            print('[clock]: no random album found')
            return
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return
    else:
        message = f":new_moon_with_face: Today's album of the day is: {album.album_url}"
        print(f'[clock]: {message}')
        slack.chat.post_message(channel, message, unfurl_links=True)


sched.start()
