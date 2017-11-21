import collections
from contextlib import closing

import psycopg2

from albumlist.models import DatabaseError, get_connection


def create_list_table():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('CREATE TABLE list (id serial PRIMARY KEY, album varchar);')
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_list():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT album FROM list;')
            return [item[0] for item in cur.fetchall()]
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_list_count():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT album FROM list;')
            return cur.rowcount
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def add_to_list(album_id):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('INSERT INTO list (album) VALUES (%s)', (album_id,))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def add_many_to_list(album_ids):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.executemany('INSERT INTO list (album) VALUES (%s)', album_ids)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def delete_from_list(album_id):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM list where album = %s;', (album_id,))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


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


def _reset_list():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM list')
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def de_dup():
    duplicates = [
        (album_id, )
        for album_id, count in collections.Counter(get_list()).items()
        if count > 1
    ]
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.executemany('DELETE FROM list where album = %s;', duplicates)
            cur.executemany('INSERT INTO list (album) VALUES (%s)', duplicates)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)