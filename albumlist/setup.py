import collections
import csv
import datetime
import functools
import io
import json
import logging
import os
import re
import sys

import flask
from flask_cacheify import init_cacheify
from pathlib import Path
import requests

from albumlist import constants
from albumlist.scrapers import NotFoundError, links, bandcamp
from albumlist.models import DatabaseError
from albumlist.models import albums as albums_model, list as list_model


def add_blueprints(application):
    from albumlist.views.api import api_blueprint
    application.register_blueprint(api_blueprint)
    api_blueprint.config = application.config.copy()

    from albumlist.views.site import site_blueprint
    application.register_blueprint(site_blueprint)
    site_blueprint.config = application.config.copy()

    from albumlist.views.slack import slack_blueprint
    application.register_blueprint(slack_blueprint)
    slack_blueprint.config = application.config.copy()


def create_tables(app):
    try:
        list_model.create_list_table()
        albums_model.create_albums_table()
        albums_model.create_albums_index()
    except DatabaseError as e:
        app.logger.error(f'[db]: ERROR - {e}')


def create_app():
    TEMPLATE_DIR = Path(__file__).parent.joinpath('templates')
    
    app = flask.Flask(__name__, template_folder=TEMPLATE_DIR)
    if 'DYNO' in os.environ:
        app.logger.addHandler(logging.StreamHandler(sys.stdout))
        app.logger.setLevel(logging.INFO)
    app.config.from_object(os.environ['APP_SETTINGS'])

    # check required config variables
    LIST_NAME = app.config['LIST_NAME']
    APP_TOKENS = app.config['APP_TOKENS']

    create_tables(app)

    add_blueprints(app)

    app.cache = init_cacheify(app)

    app.db_error_message = f'{LIST_NAME} error - check with admin'
    app.not_found_message = f'Album not found in the {LIST_NAME}'

    def get_and_set_album_details(album_id):
        try:
            details = albums_model.get_album_details(album_id)
        except DatabaseError as e:
            flask.current_app.cache.delete('alb-' + album_id)
            raise e
        else:
            flask.current_app.cache.set('alb-' + album_id, details, 60 * 15)
        return details

    def get_cached_album_details(album_id):
        return flask.current_app.cache.get('alb-' + album_id) or flask.current_app.get_and_set_album_details(album_id)

    app.get_and_set_album_details = get_and_set_album_details
    app.get_cached_album_details = get_cached_album_details

    app.logger.info(f'[app]: created with {os.environ["APP_SETTINGS"]}')

    from albumlist.delayed import queued
    queued.deferred_ping_albumlistbot.delay()

    return app
