import os
import requests

from albumlist import delayed


message = f'Today\'s album of the day from the {os.environ.get('LIST_NAME')} is: {url}'
error_message = 'Odd... Something went wrong.'
url = f'https://{os.environ.get('LIST_NAME')}.herokuapp.com/slack/random'
data = {'token': os.environ.get('SLACK_APP_TOKEN')} 
channel = "C0A8M8B9Q" # announcements


@delayed.queue_func
def produce_album_of_the_day():
    response = requests.post(url, data=data)
    if not response.ok or response.content == '':
        print(f'[error]: {error_message}')
    else:
        response = response.json()
        response['channel'] = channel
        response['text'] = message.format(url=response['text'])
        print(f'{response}')


if __name__ == '__main__':
	produce_album_of_the_day.delay()