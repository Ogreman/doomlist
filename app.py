import flask
import requests
import os
import json
import psycopg2
import urlparse
import slacker
import collections
import datetime

from scrapers import scrapers
from delayed import delayed


QUEUE_NAME = 'deferred_queue'
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
BOT_URL = "***REMOVED***"


urlparse.uses_netloc.append("postgres")
url = urlparse.urlparse(os.environ["DATABASE_URL"])

app = flask.Flask(__name__)
app.config['REDIS_QUEUE_KEY'] = QUEUE_NAME


class DatabaseError(Exception): pass


def create_logs_table():
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("CREATE TABLE logs (id serial PRIMARY KEY, message varchar);")
        conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def create_list_table():
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("CREATE TABLE list (id serial PRIMARY KEY, album varchar);")
        conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def add_to_logs(message):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute('INSERT INTO logs (message) VALUES (%s)', (message,))
        conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


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


def get_logs():
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("SELECT message FROM logs;")
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


@delayed.queue_func
def deferred_scrape(scrape_function, callback, response_url=BOT_URL):
    try:
        slack = slacker.Slacker(API_TOKEN)
        response = slack.channels.history(CHANNEL_ID)
    except slacker.Error:
        message = 'There was an error accessing the Slack API'
    else:
        if response.successful:
            messages = response.body.get('messages', [])
            results = scrape_function(messages)
            album_ids = check_for_new_ids(results)
            try:    
                if album_ids:
                    callback(album_ids)
            except DatabaseError:
                message = 'Failed to update list'
            else:
                message = 'Finished checking for new albums: %d found.' % (len(album_ids), )
        else:
            message = 'Failed to get channel history'
    if response_url:
        requests.post(
            response_url,
            data=json.dumps(
                {'text': message}
            )
        )


@delayed.queue_func
def deferred_consume(message, scrape_function, callback, response_url=BOT_URL):
    try:
        album_id = scrape_function(message)
    except scrapers.NotFoundError:
        message = None
    else:
        if album_id not in get_list():
            try:    
                callback(album_id)
            except DatabaseError:
                message = 'Failed to update list'
            else:
                message = 'Added album to list'
        else:
            message = 'Album already in list'
    if response_url and message is not None:
        requests.post(
            response_url,
            data=message
        )


@app.route('/consume', methods=['POST'])
def consume():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        deferred_consume.delay(
            form_data,
            scrapers.scrape_bandcamp_album_ids_from_urls,
            add_to_list,
        )
    return '', 200


@app.route('/list', methods=['GET'])
def list_albums():
    try:
        response = flask.Response(json.dumps(get_list()))
    except DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/logs', methods=['GET'])
def list_logs():
    try:
        response = flask.Response(json.dumps(get_logs()))
    except DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
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
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        deferred_scrape.delay(
            scrapers.scrape_bandcamp_album_ids,
            add_many_to_list,
            form_data.get('response_url', BOT_URL),
        )
        return 'Scrape request sent', 200
    return '', 200


if __name__ == "__main__":
    app.run(debug=os.environ.get('BC_DEBUG', True))

