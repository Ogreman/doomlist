import os
import requests

from delayed import delayed


message = "Today's album of the day from the Doomlist is: {url}"
error_message = "Odd... Something went wrong."
url = "https://doomlist.herokuapp.com/slack/random"
data = {'token': os.environ.get('SLACK_APP_TOKEN')} 
channel = "C0A8M8B9Q" # announcements


@delayed.queue_func
def produce_album_of_the_day():
    response = requests.post(url, data=data)
    if not response.ok or response.content == '':
        print '[error]: ' + error_message
    else:
        response = response.json()
        response['channel'] = channel
        response['text'] = message.format(url=response['text'])
        print response


if __name__ == '__main__':
	produce_album_of_the_day.delay()