import flask

from doomlist.models import DatabaseError
from doomlist.models import albums as albums_model


site_blueprint = flask.Blueprint(name='site',
                               import_name=__name__,
                               url_prefix='')


@site_blueprint.route('/', methods=['GET'])
def embedded_random():
    try:
        album_id, name, artist, album_url, _ = albums_model.get_random_album()
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return flask.current_app.db_error_message, 500
    except TypeError:
        return flask.current_app.not_found_message, 404
    return flask.render_template('index.html', list_name=list_name, album_id=album_id, name=name, artist=artist, album_url=album_url)