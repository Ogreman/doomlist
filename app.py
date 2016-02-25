from __future__ import absolute_import

import flask
import requests
import os
import json
import psycopg2
import urlparse
import slacker
import threading
import collections


from scrapers import scrapers


urlparse.uses_netloc.append("postgres")
url = urlparse.urlparse(os.environ["DATABASE_URL"])


app = flask.Flask(__name__)


APP_TOKENS = [
    "***REMOVED***", 
    "***REMOVED***",
    "***REMOVED***",
    "***REMOVED***",
]
COMMENT = '<!-- album id '
COMMENT_LEN = len(COMMENT)
CHANNEL_ID = '***REMOVED***'
CHANNEL_NAME = 'streamshare'
API_TOKEN = '***REMOVED***'
BOT_URL = "https://doomsters.slack.com/services/hooks/slackbot?token=ZDwAB8bUIrE0zthovM90MB25&channel=%23{channel}"



class DatabaseError(Exception): pass


def add_to_list(album_id):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        if album_id not in get_list():
            cur.execute('INSERT INTO list (album) VALUES (%s)', (album_id,))
            conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def de_dup():
    duplicates = [
        (album_id, )
        for album_id, count in collections.Counter(get_list()).items()
        if count > 1
    ]
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.executemany("DELETE FROM list where album = %s;", duplicates)
        cur.executemany('INSERT INTO list (album) VALUES (%s)', duplicates)
        conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def add_many_to_list(album_ids):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.executemany('INSERT INTO list (album) VALUES (%s)', album_ids)
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


def delete_album(album):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("DELETE FROM list where album = %s;", (album,))
        conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


@app.route('/consume', methods=['POST'])
def consume():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        try:
            album_id = scrapers.scrape_bandcamp_album_ids_from_urls(form_data)
            add_to_list(album_id)
        except DatabaseError:
            return json.dumps({'text': 'Failed to update database'}), 200
        except scrapers.NotFoundError:
            pass
        else:
            return json.dumps({'text': 'Added to Bandcamp album list'}), 200
    return '', 200


@app.route('/list', methods=['GET'])
def list_albums():
    try:
        response = flask.Response(json.dumps(get_list()))
    except DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/delete', methods=['POST'])
def delete():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        album_id = form_data.get('text')
        if album_id:
            try:
                delete_album(album_id.strip())
            except DatabaseError:
                return 'Failed to delete album', 200
            else:
                return 'Deleted album', 200
    return '', 200


@app.route('/add', methods=['POST'])
def add():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        album_id = form_data.get('text')
        if album_id:
            try:
                add_to_list(album_id.strip())
            except DatabaseError:
                return 'Failed to add new album', 200
            else:
                return 'Added new album', 200
    return '', 200


@app.route('/scrape', methods=['POST'])
def scrape():

    def check_for_new_ids(results):
        return [
            (str(album_id),)
            for album_id in set(
                results
            ).difference(
                set(get_list())
            )
            if album_id is not None
        ]

    def deferred_scrape(response_url, scrape_function, callback):
        slack = slacker.Slacker(API_TOKEN)
        response = slack.channels.history(CHANNEL_ID)
        if response.successful:
            messages = response.body.get('messages', [])
            results = scrape_function(messages)
            album_ids = check_for_new_ids(results)
            if album_ids:
                callback(album_ids)
            if response_url:
                requests.post(
                    response_url,
                    data=json.dumps(
                        {'text': 'Finished checking for new albums: %d found.' % (len(album_ids), )}
                    )
                )

    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        thread = threading.Thread(
            target=deferred_scrape,
            args=(
                form_data.get('response_url'),
                scrapers.scrape_bandcamp_album_ids,
                add_many_to_list,
            ),
        )
        thread.setDaemon(True)
        thread.start()
        return 'Scrape request sent', 200
    return '', 200


if __name__ == "__main__":
    app.run(debug=os.environ.get('BC_DEBUG', True))

