import re
import os
import json
import collections
import datetime
import requests
import flask
import slacker
import csv
import functools
import io

from albumlist import constants
from albumlist.scrapers import NotFoundError, links, bandcamp
from albumlist.models import DatabaseError
from albumlist.models import albums as albums_model, list as list_model

from flask_cacheify import init_cacheify
from pathlib import Path


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


def create_app():
    TEMPLATE_DIR = Path(__file__).parent.joinpath('templates')
    
    app = flask.Flask(__name__, template_folder=TEMPLATE_DIR)
    app.config.from_object(os.environ['APP_SETTINGS'])

    # check required config variables
    LIST_NAME = app.config['LIST_NAME']
    API_TOKEN = app.config['SLACK_API_TOKEN']
    CLIENT_ID = app.config['SLACK_CLIENT_ID']
    CLIENT_SECRET = app.config['SLACK_CLIENT_SECRET']
    SLACK_TEAM = app.config['SLACK_TEAM']
    BOT_URL_TEMPLATE = app.config['BOT_URL_TEMPLATE']
    DEFAULT_CHANNEL = app.config['DEFAULT_CHANNEL']
    SLACKBOT_TOKEN = app.config['SLACKBOT_TOKEN']
    ADMIN_IDS = app.config['ADMIN_IDS']
    APP_TOKENS = app.config['APP_TOKENS']
    SCRAPE_CHANNEL_ID = app.config['SCRAPE_CHANNEL_ID']

    app.config['BOT_URL_TEMPLATE'] = BOT_URL_TEMPLATE.format(team=SLACK_TEAM, token=SLACKBOT_TOKEN, channel='{channel}')
    app.config['DEFAULT_BOT_URL'] = app.config['BOT_URL_TEMPLATE'].format(channel=DEFAULT_CHANNEL)

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

    return app
