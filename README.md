# Tagarela (EXPERIMETAL!!!)

Microservice for comments.

Similar to [Isso](https://posativ.org/isso/), but using [Viralata](https://gitlab.com/ok-br/viralata) for authentication.

An example of web interface using this microservice as backend is [Cuidando2](https://gitlab.com/ok-br/cuidando2).


## Install

```
$ python setup.py install
```

If you are using Postgres:

```
$ pip install psycopg2
```

## Prepare DB

Create the database and user, set them in `settings/local_settings.py` as `SQLALCHEMY_DATABASE_URI`.

```python
SQLALCHEMY_DATABASE_URI = 'postgresql://<user>:<password>@localhost/<database>'
```

Create tables:

```
$ python manage.py initdb
```

## Run!

```
$ python manage.py run
```

## API

Needs doc...

## Name

Tagarela, in brazilian portuguese, means a person who talks alot...
