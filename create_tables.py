from models import models


if __name__ == '__main__':
    try:
        models.create_logs_table()
        models.create_list_table()
        models.create_albums_table()
        models.create_albums_index()
        models.create_votes_table()
    except models.DatabaseError as e:
        print "[db]: ERROR - " + str(e)