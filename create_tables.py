from albumlist.models import DatabaseError
from albumlist.models.albums import create_albums_table, create_albums_index
from albumlist.models.list import create_list_table


if __name__ == '__main__':
    try:
        create_list_table()
        create_albums_table()
        create_albums_index()
    except DatabaseError as e:
        print(f'[db]: ERROR - {e}')