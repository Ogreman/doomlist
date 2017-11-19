import os
import psycopg2
import collections
from urllib.parse import urlparse
from contextlib import closing


# urlparse.uses_netloc.append("postgres")


def get_connection():
    db_url = urlparse(os.environ['DATABASE_URL'])
    try:
        return psycopg2.connect(
            database=db_url.path[1:],
            user=db_url.username,
            password=db_url.password,
            host=db_url.hostname,
            port=db_url.port
        )
    except psycopg2.OperationalError as e:
        raise DatabaseError(e)


class DatabaseError(Exception): 
    pass


def add_column(table, col, col_type):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(f'ALTER TABLE {table} ADD {col} {col_type}')
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


# def create_logs_table():
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('CREATE TABLE logs (id serial PRIMARY KEY, message varchar);')
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


def create_list_table():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('CREATE TABLE list (id serial PRIMARY KEY, album varchar);')
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def create_albums_table():
    sql = """
        CREATE TABLE albums (
        id varchar PRIMARY KEY,
        artist varchar DEFAULT '',
        name varchar DEFAULT '',
        url varchar DEFAULT '',
        img varchar DEFAULT '',
        channel varchar DEFAULT '',
        available boolean DEFAULT true, 
        added timestamp DEFAULT now()
        );"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def create_albums_index():
    sql = """
        CREATE INDEX alb_lo_name 
        ON albums (
        LOWER(name)
        );"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def create_tags_table():
    sql = """
        CREATE TABLE tags (
        tag varchar PRIMARY KEY
        );"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def create_album_tags_table():
    sql = """
        CREATE TABLE album_tags (
        album varchar REFERENCES albums (id), 
        tag varchar REFERENCES tags (tag),

        CONSTRAINT id_tag UNIQUE (album, tag)
        );"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


# def create_votes_table():
#     sql = """
#         CREATE TABLE votes (
#         id serial PRIMARY KEY, 
#         album varchar
#         );"""
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute(sql)
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


# def add_to_votes(album_id):
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('INSERT INTO votes (album) VALUES (%s)', (album_id,))
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


# def add_to_logs(message):
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('INSERT INTO logs (message) VALUES (%s)', (message,))
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError


def add_to_list(album_id):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('INSERT INTO list (album) VALUES (%s)', (album_id,))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def add_to_albums(album_id, artist, name, url, img='', channel=''):
    sql = """
        INSERT INTO albums (
        id, 
        artist, 
        name, 
        url, 
        img,
        channel, 
        available
        ) VALUES (%s, %s, %s, %s, %s, %s, %s);"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (album_id, artist, name, url, img, channel, True))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def add_to_tags(tag):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('INSERT INTO tags (tag) VALUES (%s)', (tag,))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def tag_album(album_id, tag):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('INSERT INTO album_tags (album, tag) VALUES (%s, %s)', (album_id, tag))
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


def add_many_to_list(album_ids):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.executemany('INSERT INTO list (album) VALUES (%s)', album_ids)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def add_many_to_albums(albums):
    sql = """
        INSERT INTO albums (
        id, 
        artist, 
        name, 
        url, 
        img
        ) VALUES (%s, %s, %s, %s, %s);"""
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.executemany(sql, albums)
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def add_img_to_album(album_id, album_img):
    with closing(get_connection()) as conn:
        try:
            sql = """
                UPDATE albums
                SET img = %s
                WHERE id = %s;
                """
            cur = conn.cursor()
            cur.execute(sql, (album_img, album_id))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def add_added_to_album(album_id, dt):
    with closing(get_connection()) as conn:
        try:
            sql = """
                UPDATE albums
                SET added = %s
                WHERE id = %s;
                """
            cur = conn.cursor()
            cur.execute(sql, (dt, album_id))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def update_album_availability(album_id, status):
    with closing(get_connection()) as conn:
        try:
            sql = """
                UPDATE albums
                SET available = %s
                WHERE id = %s;
                """
            cur = conn.cursor()
            cur.execute(sql, (bool(status), album_id))
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


# def get_votes_count(album_id):
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('SELECT * FROM votes WHERE album = %s;', (album_id,))
#             return cur.rowcount
#         except (psycopg2.ProgrammingError, psycopg2.InternalError):
#             raise DatabaseError


# def get_votes():
#     sql = """
#         SELECT votes.album, artist, name, count(DISTINCT votes.id) 
#         FROM votes 
#         JOIN albums on votes.album = albums.id 
#         GROUP BY votes.album, albums.artist, albums.name 
#         """
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute(sql)
#             return cur.fetchall()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError):
#             raise DatabaseError


# def get_top_votes(count=5):
#     sql = """
#         SELECT votes.album, artist, name, count(DISTINCT votes.id) 
#         FROM votes 
#         JOIN albums on votes.album = albums.id 
#         GROUP BY votes.album, albums.artist, albums.name 
#         ORDER BY count(DISTINCT votes.id) DESC;
#         """
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute(sql)
#             return cur.fetchmany(count)
#         except (psycopg2.ProgrammingError, psycopg2.InternalError):
#             raise DatabaseError


def get_albums():
    sql = """
        SELECT id, name, artist, url, img, available, channel, added
        FROM albums
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_by_channel(channel):
    sql = """
        SELECT id, name, artist, url, img, channel, added
        FROM albums
        WHERE channel = %s
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (channel,))
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_with_tags():
    sql = """
        SELECT id, name, artist, url, img, channel, added, album_tags.tag
        FROM albums
        LEFT JOIN album_tags on albums.id = album_tags.album;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_by_channel_with_tags(channel):
    sql = """
        SELECT id, name, artist, url, img, channel, added, album_tags.tag
        FROM albums
        WHERE channel = %s
        LEFT JOIN album_tags on albums.id = album_tags.album;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (channel,))
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_unavailable():
    sql = """
        SELECT id, name, artist, url, added
        FROM albums 
        WHERE available = false;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_count():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT id FROM albums;')
            return cur.rowcount
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)

        
def get_album_details(album_id):
    sql = """
        SELECT id, name, artist, url, img, available, channel, added
        FROM albums 
        WHERE id = %s;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (album_id, ))
            return cur.fetchone()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
    

def get_album_details_from_ids(album_ids):
    sql = """
        SELECT id, artist, name, url, img, available, channel, added
        FROM albums 
        WHERE id IN %s;
        """
    with closing(get_connection()) as conn:        
        try:
            cur = conn.cursor()
            cur.execute(sql, (album_ids, ))
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_album_ids():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT id FROM albums;')
            return [c[0] for c in cur.fetchall()]
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
    

# def get_logs():
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('SELECT message FROM logs;')
#             return [item[0] for item in cur.fetchall()]
#         except (psycopg2.ProgrammingError, psycopg2.InternalError):
#             raise DatabaseError


def get_tags():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT tag FROM tags;')
            return [item[0] for item in cur.fetchall()]
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_album_tags(album_id):
    sql = """
        SELECT tag 
        FROM album_tags 
        WHERE album = %s;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (album_id,))
            return [item[0] for item in cur.fetchall()]
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
    

def delete_from_albums(album_id):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM albums where id = %s;', (album_id,))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def delete_from_list_and_albums(album_id):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM albums where id = %s;', (album_id,))
            cur.execute('DELETE FROM list where album = %s;', (album_id,))
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def _reset_list():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM list')
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
    

def _reset_albums():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM albums')
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


# def _reset_votes():
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('DELETE FROM votes')
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError):
#             raise DatabaseError


def search_albums(query):
    sql = """
        SELECT id, name, artist, url, img, channel, added, album_tags.tag
        FROM albums 
        LEFT JOIN album_tags on albums.id = album_tags.album
        WHERE LOWER(name) LIKE %s 
        OR LOWER(artist) LIKE %s
        OR id IN (
            SELECT album
            FROM album_tags
            WHERE tag LIKE %s
        )
        AND available = true;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            term = f'%{query}%'
            cur.execute(sql, (term, term, term))
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def search_albums_by_tag(query):
    sql = """
        SELECT id, name, artist, url, img, channel, added, album_tags.tag
        FROM albums 
        LEFT JOIN album_tags on albums.id = album_tags.album
        WHERE id IN (
            SELECT album
            FROM album_tags
            WHERE tag LIKE %s
        )
        AND available = true;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            term = f'%{query}%'
            cur.execute(sql, (term, ))
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_by_tag(tag):
    sql = """
        SELECT id, name, artist, url, img, channel, added, album_tags.tag
        FROM albums 
        LEFT JOIN album_tags on albums.id = album_tags.album
        WHERE id IN (
            SELECT album
            FROM album_tags
            WHERE tag = %s
        )
        AND available = true;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (tag, ))
            return cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_random_album():
    sql = """
        SELECT id, name, artist, url, img 
        FROM albums 
        WHERE available = true
        ORDER BY RANDOM() 
        LIMIT 1;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return cur.fetchone()
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


def check_for_new_albums():
    return [
        str(album_id)
        for album_id in set(get_list()).difference(set(get_album_ids()))
        if album_id is not None
    ]
