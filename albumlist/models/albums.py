from contextlib import closing

import psycopg2

from albumlist.models import DatabaseError, get_connection
from albumlist.models.list import get_list


class Album(object):

    def __init__(self, album_id, name, artist, url, img, channel, available, added, tag=None):
        self.album_id = album_id
        self.album_artist = artist
        self.album_name = name
        self.album_url = url
        self.album_image = img
        self.channel = channel
        self.available = available
        self.added = added
        self.tag = tag

    def to_dict(self):
        return {
            'added': self.added.isoformat() or '',
            'album': self.album_name or '',
            'artist': self.album_artist or '',
            'channel': self.channel or '',
            'img': self.album_image or '',
            'tags': [self.tag] if self.tag else [],
            'url': self.album_url or '',
        }

    @classmethod
    def from_values(cls, values):
        return cls(*values)

    @classmethod
    def albums_from_values(cls, list_of_values):
        for values in list_of_values:
            yield cls.from_values(values)

    @staticmethod
    def details_map_from_albums(albums):
        details = dict()
        for album in albums:
            if album.album_id not in details:
                details[album.album_id] = album.to_dict()
            elif album.tag:
                details[album.album_id]['tags'].append(album.tag)
        return details


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


def get_albums():
    sql = """
        SELECT id, name, artist, url, img, available, channel, added
        FROM albums
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return Album.albums_from_values(cur.fetchall())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_with_tags():
    sql = """
        SELECT id, name, artist, url, img, available, channel, added, album_tags.tag
        FROM albums
        LEFT JOIN album_tags on albums.id = album_tags.album;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return Album.albums_from_values(cur.fetchall())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_by_channel_with_tags(channel):
    sql = """
        SELECT id, name, artist, url, img, available, channel, added, album_tags.tag
        FROM albums
        LEFT JOIN album_tags on albums.id = album_tags.album
        WHERE channel = %s;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (channel,))
            return Album.albums_from_values(cur.fetchall())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_available():
    sql = """
        SELECT id, name, artist, url, img, available, channel, added
        FROM albums
        WHERE available = true;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return Album.albums_from_values(cur.fetchall())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_unavailable():
    sql = """
        SELECT id, name, artist, url, img, available, channel, added
        FROM albums 
        WHERE available = false;
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return Album.albums_from_values(cur.fetchall())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_without_covers():
    sql = """
        SELECT id, name, artist, url, img, available, channel, added
        FROM albums
        WHERE img = '';
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return Album.albums_from_values(cur.fetchall())
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


def get_albums_unavailable_count():
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute('SELECT id FROM albums WHERE available = false;')
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
            return Album.from_values(cur.fetchone())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
    

def get_album_details_with_tags(album_id):
    sql = """
        SELECT id, name, artist, url, img, available, channel, added, album_tags.tag
        FROM albums
        LEFT JOIN album_tags on albums.id = album_tags.album
        WHERE id = %s;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (album_id, ))
            return Album.albums_from_values(cur.fetchall())
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
            return Album.albums_from_values(cur.fetchall())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_by_channel(channel):
    sql = """
        SELECT id, name, artist, url, img, available, channel, added
        FROM albums
        WHERE channel = %s
    """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql, (channel,))
            return Album.albums_from_values(cur.fetchall())
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
        except psycopg2.IntegrityError:
            raise DatabaseError(f'album {album_id} already exists')
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


def update_album_added(album_id, added):
    with closing(get_connection()) as conn:
        try:
            sql = """
                UPDATE albums
                SET added = %s
                WHERE id = %s;
                """
            cur = conn.cursor()
            cur.execute(sql, (added, album_id))
            conn.commit()
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


def get_random_album():
    sql = """
        SELECT id, name, artist, url, img, available, channel, added
        FROM albums 
        WHERE available = true
        ORDER BY RANDOM() 
        LIMIT 1;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            return Album.from_values(cur.fetchone())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def get_albums_by_tag(tag):
    sql = """
        SELECT id, name, artist, url, img, available, channel, added, album_tags.tag
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
            return Album.albums_from_values(cur.fetchall())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def search_albums(query):
    sql = """
        SELECT id, name, artist, url, img, available, channel, added, album_tags.tag
        FROM albums 
        LEFT JOIN album_tags on albums.id = album_tags.album
        WHERE LOWER(name) LIKE %s 
        OR LOWER(artist) LIKE %s
        OR id IN (
            SELECT album
            FROM album_tags
            WHERE LOWER(tag) LIKE %s
        )
        AND available = true;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            term = f'%{query}%'
            cur.execute(sql, (term, term, term))
            return Album.albums_from_values(cur.fetchall())
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)


def search_albums_by_tag(query):
    sql = """
        SELECT id, name, artist, url, img, available, channel, added, album_tags.tag
        FROM albums 
        LEFT JOIN album_tags on albums.id = album_tags.album
        WHERE id IN (
            SELECT album
            FROM album_tags
            WHERE LOWER(tag) LIKE %s
        )
        AND available = true;
        """
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            term = f'%{query}%'
            cur.execute(sql, (term, ))
            return Album.albums_from_values(cur.fetchall())
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


def check_for_new_albums():
    return [
        str(album_id)
        for album_id in set(get_list()).difference(set(get_album_ids()))
        if album_id is not None
    ]
