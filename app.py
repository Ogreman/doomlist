import os
import json
import datetime
import collections
import urlparse
import psycopg2
import requests
import flask
import slacker

from scrapers import scrapers
from delayed import delayed
from flask.ext.cacheify import init_cacheify


APP_TOKENS = [
    "***REMOVED***", 
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
app.config.from_object(os.environ['APP_SETTINGS'])
app.cache = init_cacheify(app)


class DatabaseError(Exception): 
    pass


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


def create_albums_table():
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("CREATE TABLE albums (id varchar PRIMARY KEY, artist varchar, name varchar);")
        conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def create_votes_table():
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("CREATE TABLE votes (id serial PRIMARY KEY, album varchar);")
        conn.commit()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def add_to_votes(album_id):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute('INSERT INTO votes (album) VALUES (%s)', (album_id,))
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


def add_to_albums(album_id, artist, name):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute('INSERT INTO albums (id, artist, name) VALUES (%s, %s, %s)', (album_id, artist, name))
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


def add_many_to_albums(albums):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.executemany('INSERT INTO albums (id, artist, name) VALUES (%s, %s, %s)', albums)
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


def get_votes_count(album_id):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("SELECT * FROM votes WHERE album = %s;", (album_id,))
        return cur.rowcount
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def get_albums():
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("SELECT id, name, artist FROM albums;")
        return cur.fetchall()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def get_album_details(album_id):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("SELECT id, name, artist FROM albums WHERE id = %s;", (album_id, ))
        return cur.fetchone()
    except (psycopg2.ProgrammingError, psycopg2.InternalError):
        raise DatabaseError
    finally:
        cur.close()
        conn.close()


def get_album_ids():
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("SELECT id FROM albums;")
        return [c[0] for c in cur.fetchall()]
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


def check_for_new_list_ids(results):
    return [
        (str(album_id),)
        for album_id in set(
            results
        ).difference(
            set(get_list())
        )
        if album_id is not None
    ]


def check_for_new_albums():
    return [
        str(album_id)
        for album_id in set(get_list()).difference(set(get_album_ids()))
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
            album_ids = check_for_new_list_ids(results)
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
def deferred_consume(text, scrape_function, callback, response_url=BOT_URL):
    try:
        album_id = scrape_function(text)
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
                deferred_process_album_details.delay(album_id)
        else:
            message = 'Album already in list'
    if response_url and message is not None:
        requests.post(
            response_url,
            data=message
        )


@delayed.queue_func
def deferred_process_all_album_details(response_url=BOT_URL):
    def get_album_details_from_ids():
        for album_id in check_for_new_albums():
            try:
                album, artist = scrapers.scrape_album_details_from_id(album_id)
                yield (album_id, artist, album)
            except (TypeError, ValueError):
                continue
    try:
        add_many_to_albums(list(get_album_details_from_ids()))
    except DatabaseError:
        pass
    else:
        if response_url:
            requests.post(response_url, data='Processed all album details')


@delayed.queue_func
def deferred_process_album_details(album_id):
    try:
        album, artist = scrapers.scrape_album_details_from_id(album_id)
        add_to_albums(album_id, artist, name)
    except (TypeError, ValueError, DatabaseError):
        pass


@app.route('/consume', methods=['POST'])
def consume():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        deferred_consume.delay(
            form_data.get('text', ''),
            scrapers.scrape_bandcamp_album_ids_from_url,
            add_to_list,
        )
    return '', 200


@app.route('/list', methods=['GET'])
@app.cache.cached(timeout=1800)
def list_albums():
    try:
        response = flask.Response(json.dumps(get_list()))
    except DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/albums', methods=['GET'])
@app.cache.cached(timeout=1800)
def list_album_details():
    try:
        details = [
            {
                album_id: {
                    'artist': artist,
                    'album': album,
                }
            }
            for album_id, album, artist in get_albums()
        ]
        response = flask.Response(json.dumps(details))
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


@app.route('/proc', methods=['POST'])
def proc():
    form_data = flask.request.form
    if form_data.get('token') in APP_TOKENS:
        deferred_process_all_album_details.delay(
            form_data.get('response_url', BOT_URL)
        )
        return 'Process request sent', 200
    return '', 200


@app.route('/album/<album_id>', methods=['GET'])
@app.cache.cached(timeout=86400)
def album(album_id):
    try:
        response = flask.Response(json.dumps({
            'text': 'Success',
            'album': dict(zip(
                ('id', 'name', 'artist'),
                get_album_details(album_id),
            ))
        }))
    except (DatabaseError, TypeError):
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/votes/<album_id>', methods=['GET'])
def votes(album_id):
    try:
        response = flask.Response(json.dumps({
            'text': 'Success', 
            'value': get_votes_count(album_id),
        }))
    except DatabaseError:
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/vote', methods=['POST'])
def vote():
    form_data = flask.request.form
    try:
        album_id = form_data['album_id']
        add_to_votes(album_id)
        response = flask.Response(json.dumps({
            'text': 'Success', 
            'value': get_votes_count(album_id),
        }))
    except (DatabaseError, KeyError):
        response = flask.Response(json.dumps({'text': 'Failed'}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


if __name__ == "__main__":
    app.run(debug=os.environ.get('DEBUG', True))

