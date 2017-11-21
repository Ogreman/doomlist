from albumlist.models import DatabaseError
from albumlist.models.albums import create_albums_table, create_albums_index
from albumlist.models.list import create_list_table
from albumlist.models.tags import create_tags_table, create_album_tags_table


if __name__ == '__main__':
    try:
        # models.create_logs_table()
        # models.create_votes_table()
        create_list_table()
        create_albums_table()
        create_albums_index()
        create_tags_table()
        create_album_tags_table()
    except DatabaseError as e:
        print(f'[db]: ERROR - {e}')