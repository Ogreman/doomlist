import os


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')
    REDIS_QUEUE_KEY = 'deferred_queue'
    API_TOKEN = os.environ.get('API_TOKEN')
    BOT_URL_TEMPLATE = os.environ.get('BOT_URL_TEMPLATE')
    DEFAULT_CHANNEL = os.environ.get('DEFAULT_CHANNEL')
    URL_REGEX = "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    ALBUM_TEMPLATE = "{name} by {artist}: {url}"
    BANDCAMP_URL_TEMPLATE = "https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=large/artwork=small"
    APP_TOKENS = [
        token for key, token in os.environ.items()
        if key.startswith('APP_TOKEN')
    ]
    ADMIN_IDS = [
        user_id for key, user_id in os.environ.items()
        if key.startswith('ADMIN_ID')
    ]


class ProductionConfig(Config):
    DEBUG = False
    CACHE_TYPE = "memcached"


class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    CACHE_TYPE = "simple"


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True
    CACHE_TYPE = "simple"


class TestingConfig(Config):
    TESTING = True
