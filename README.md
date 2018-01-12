# Albumlist Slack App

This is a [Slack](https://slack.com/) app that scrapes and compiles lists of ([bandcamp](https://www.bandcamp.com)) albums that have been shared by a Slack team.

Once deployed, use the [albumlistbot](https://slack.com/oauth/authorize?client_id=10066701634.66761250224&scope=commands,links:read,chat:write:bot,channels:history) to register your Slack team with your new Albumlist.

## Deploy to Heroku

You can deploy this app yourself to [Heroku](https://heroku.com/) to play with - though I would suggest forking this repository first and tweaking the environment variables listed under "env" in the [app.json file](https://github.com/Ogreman/albumlist/blob/master/app.json).

[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy)

## Running services locally

Using [Docker Compose](https://docs.docker.com/compose/install/):

```
# create a local .env file to be consumed by the daemon and albumlist
$ cat .env
APP_SETTINGS=config.DevelopmentConfig 
LIST_NAME=albumlist

$ docker-compose up -d
$ docker exec albumlist python create_tables.py
```

Use [Pyenv](https://github.com/pyenv/pyenv) to manage installed Python versions:

```
$ curl -L https://raw.githubusercontent.com/pyenv/pyenv-installer/master/bin/pyenv-installer | bash
$ pyenv versions
* system
  2.7
  3.4.7
  3.5.4
  3.6.3
```

You can then set the default global Python version using:
```
$ pyenv global 3.6.3
$ pyenv versions
  system
  2.7
  3.4.7
  3.5.4
* 3.6.3 (set by /Users/User/.pyenv/version)

# if pip is missing:
$ easy_install pip
```

NB: install Python versions with:
```
$ pyenv install 3.6.3
```

Install dependencies to a new virtual environment using [Pipenv](https://docs.pipenv.org/):

```
$ pip install -U pipenv
$ pipenv install
```

NB: pipenv will try to use pyenv to install a missing version of Python specified in the Pipfile.

Run commands within the new virtual environment with:
```
pipenv run python create_tables.py
pipenv run python run.py
```
