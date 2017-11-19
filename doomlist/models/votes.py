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

# def _reset_votes():
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('DELETE FROM votes')
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError):
#             raise DatabaseError

