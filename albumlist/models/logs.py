
# def create_logs_table():
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('CREATE TABLE logs (id serial PRIMARY KEY, message varchar);')
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError(e)


# def get_logs():
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('SELECT message FROM logs;')
#             return [item[0] for item in cur.fetchall()]
#         except (psycopg2.ProgrammingError, psycopg2.InternalError):
#             raise DatabaseError


# def add_to_logs(message):
#     with closing(get_connection()) as conn:
#         try:
#             cur = conn.cursor()
#             cur.execute('INSERT INTO logs (message) VALUES (%s)', (message,))
#             conn.commit()
#         except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
#             raise DatabaseError
