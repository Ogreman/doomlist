import flask
import jinja2

from albumlist.models import DatabaseError
from albumlist.models import albums as albums_model


site_blueprint = flask.Blueprint(name='site',
                               import_name=__name__,
                               url_prefix='')


@site_blueprint.route('/', methods=['GET'])
def embedded_random():
    try:
        album = albums_model.get_random_album()
    except DatabaseError as e:
        print('[db]: failed to get random album')
        print(f'[db]: {e}')
        return flask.current_app.db_error_message, 500
    except TypeError:
        return flask.current_app.not_found_message, 404
    if album:
        kwargs = dict(
            bot_url=site_blueprint.config['ALBUMLISTBOT_URL'],
            bookmarket_url=flask.url_for('.bookmarklet', _external=True, _scheme="https"),
            list_name=site_blueprint.config['LIST_NAME'],
            album_id=album.album_id,
            name=album.album_name,
            artist=album.album_artist,
            album_url=album.album_url
        )
        return flask.render_template('index.html', **kwargs)
    return '', 200


@site_blueprint.route('/js/bookmarklet', methods=['GET'])
def bookmarklet():
    template = jinja2.Template("""
    (function () {
        var xhr = new XMLHttpRequest();
            xhr.open("POST", "{{ url }}", true);
            xhr.onreadystatechange = function () {
                if (xhr.readyState == 4 && xhr.status == 200) {
                    console.log('Scraping: ' + window.location.href);
                } else if (xhr.readyState == 4 && xhr.status != 200) {
                    console.log('Failed');
                }
            };
            xhr.send(JSON.stringify({
                url: window.location.href
            }));
    })();
    """)
    return template.render(url=flask.url_for('api.scrape_album', _external=True))
