import re

from albumlist import constants


def scrape_links_from_attachments(messages):
    for message in messages:
        if message.get('type') == 'message':
            for attachment in message.get('attachments', []):
                try:
                    yield attachment['from_url']
                except KeyError:
                    continue


def scrape_links_from_text(text):
    return [url for url in re.findall(constants.URL_REGEX, text)]
