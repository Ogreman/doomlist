import flask
import requests
import os
import json


app = flask.Flask(__name__)


APP_TOKEN = "***REMOVED***"
COMMENT = '<!-- album id '
COMMENT_LEN = len(COMMENT)
BC_ID_LIST = 'doom.list'


@app.route('/consume', methods=['POST'])
def consume():
    form_data = flask.request.form
    if form_data.get('token') == APP_TOKEN:
        if 'bandcamp.com' in form_data.get('text', ''):
            url = form_data.get('text', '').replace('\\', '').replace('<', '').replace('>', '')
            response = requests.get(url)
            if response.ok:
                content = response.text
                if COMMENT in content:
                    pos = content.find(COMMENT)
                    album_id = content[pos + COMMENT_LEN:pos + COMMENT_LEN + 20]
                    album_id = album_id.split('-->')[0].strip()
                    with open(BC_ID_LIST, 'a+') as file_handle:
                        file_handle.write(album_id)
                    return json.dumps({'text': 'Added to Bandcamp ablum list'}), 200
    return json.dumps({'text': 'Failed to add to Bandcamp album list'}), 200


if __name__ == "__main__":
    app.run(debug=os.environ.get('BC_DEBUG', True))