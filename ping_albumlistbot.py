from application import application
from albumlist.delayed.queued import deferred_ping_albumlistbot


if __name__ == '__main__':
    with application.app_context():
        deferred_ping_albumlistbot()
