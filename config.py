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
