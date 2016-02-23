import flask
import requests
import os
import json
import psycopg2
import urlparse

urlparse.uses_netloc.append("postgres")
url = urlparse.urlparse(os.environ["DATABASE_URL"])


app = flask.Flask(__name__)


APP_TOKEN = "***REMOVED***"
COMMENT = '<!-- album id '
COMMENT_LEN = len(COMMENT)


class DatabaseError(Exception): pass


def update_database(album_id):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute('INSERT INTO list (album) VALUES (%s)', (album_id,))
        conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def get_list():
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("SELECT album FROM list;")
        return [item[0] for item in cur.fetchall()]
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


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
                    try:
                        update_database(album_id)
                    except DatabaseError:
                        return json.dumps({'text': 'Failed to update database'}), 200
                    else:
                        return json.dumps({'text': 'Added to Bandcamp album list'}), 200
    return json.dumps({'text': 'Failed to add to Bandcamp album list'}), 200


@app.route('/list', methods=['GET'])
def list():
    try:
        return json.dumps(get_list()), 200
    except DatabaseError:
        return json.dumps({'text': 'Failed'}), 500


if __name__ == "__main__":
    app.run(debug=os.environ.get('BC_DEBUG', True))

