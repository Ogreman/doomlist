from models import models


if __name__ == '__main__':
    try:
        # models.create_logs_table()
        # models.create_votes_table()
        models.create_list_table()
        models.create_albums_table()
        models.create_albums_index()
        models.create_tags_table()
        models.create_album_tags_table()
    except models.DatabaseError as e:
        print(f'[db]: ERROR - {e}')