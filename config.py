import os


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me')
    REDIS_QUEUE_KEY = 'deferred_queue'
    SLACK_TEAM = os.environ.get('SLACK_TEAM')
    SLACK_API_TOKEN = os.environ.get('SLACK_API_TOKEN')
    SLACKBOT_TOKEN = os.environ.get('SLACKBOT_TOKEN')
    BOT_URL_TEMPLATE = os.environ.get('BOT_URL_TEMPLATE')
    DEFAULT_CHANNEL = os.environ.get('DEFAULT_CHANNEL')
    SCRAPE_CHANNEL_ID = os.environ.get('SCRAPE_CHANNEL_ID')
    APP_TOKENS = [
        token for key, token in os.environ.items()
        if key.startswith('APP_TOKEN')
    ]
    ADMIN_IDS = [
        user_id for key, user_id in os.environ.items()
        if key.startswith('ADMIN_ID')
    ]
    SLACK_CLIENT_ID = os.environ.get('SLACK_CLIENT_ID')
    SLACK_CLIENT_SECRET = os.environ.get('SLACK_CLIENT_SECRET')
    LIST_NAME = os.environ.get('LIST_NAME', 'Albumlist')


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
