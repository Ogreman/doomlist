import os
from contextlib import closing

import psycopg2
from urllib.parse import urlparse


# urlparse.uses_netloc.append("postgres")

class DatabaseError(Exception): 
    pass


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


def add_column(table, col, col_type):
    with closing(get_connection()) as conn:
        try:
            cur = conn.cursor()
            cur.execute(f'ALTER TABLE {table} ADD {col} {col_type}')
            conn.commit()
        except (psycopg2.ProgrammingError, psycopg2.InternalError) as e:
            raise DatabaseError(e)
