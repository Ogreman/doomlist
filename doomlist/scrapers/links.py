def scrape_links_from_attachments(messages):
    for message in messages:
        if message.get('type') == 'message':
            for attachment in message.get('attachments', []):
                try:
                    yield attachment['from_url']
                except KeyError:
                    continue


def scrape_links_from_text(messages):
    for message in messages:
        if message.get('type') == 'message':
            text = message.get('text', '')  
            try:
                if 'http' in text:
                    yield text
            except TypeError:
                pass