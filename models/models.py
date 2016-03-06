import os
import psycopg2
import collections
import urlparse


urlparse.uses_netloc.append("postgres")
url = urlparse.urlparse(os.environ["DATABASE_URL"])


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


def get_top_votes(count=5):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("SELECT album, COUNT(*) FROM votes GROUP BY album ORDER BY COUNT(*) DESC;")
        return cur.fetchmany(count)
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


def get_album_details_from_ids(album_ids):
    try:
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        cur = conn.cursor()
        cur.execute("SELECT id, artist, name FROM albums WHERE id IN %s;", (album_ids, ))
        return cur.fetchall()
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

