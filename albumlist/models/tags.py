# from contextlib import closing

# import psycopg2

# from albumlist.models import DatabaseError, get_connection


# def create_tags_table():
#     sql = """
#         CREATE TABLE tags (
#         tag varchar PRIMARY KEY
#         );"""
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute(sql)
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


# def create_album_tags_table():
#     sql = """
#         CREATE TABLE album_tags (
#         album varchar REFERENCES albums (id), 
#         tag varchar REFERENCES tags (tag),

#         CONSTRAINT id_tag UNIQUE (album, tag)
#         );"""
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute(sql)
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


# def get_tags():
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('SELECT tag FROM tags;')
#             return [item[0] for item in cur.fetchall()]
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


# def get_album_tags(album_id):
#     sql = """
#         SELECT tag 
#         FROM album_tags 
#         WHERE album = %s;
#         """
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute(sql, (album_id,))
#             return [item[0] for item in cur.fetchall()]
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


# def add_to_tags(tag):
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('INSERT INTO tags (tag) VALUES (%s)', (tag,))
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


# def tag_album(album_id, tag):
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('INSERT INTO album_tags (album, tag) VALUES (%s, %s)', (album_id, tag))
#             conn.commit()
#         except psycopg2.IntegrityError:
#             raise DatabaseError(f'album {album_id} already tagged with {tag}')
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)
    
