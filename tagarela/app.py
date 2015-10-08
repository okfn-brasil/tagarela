#!/usr/bin/env python
# coding: utf-8

import os

from flask import Flask
from flask.ext.cors import CORS
from flask.ext.restplus import apidoc
from flask.ext.mail import Mail
from itsdangerous import URLSafeTimedSerializer

from extensions import db, sv
from views import api


def create_app(settings_folder):
    # App
    app = Flask(__name__)
    app.config.from_pyfile(
        os.path.join('..', 'settings', 'common.py'), silent=False)
        # os.path.join(settings_folder, 'common.py'), silent=False)
    app.config.from_pyfile(
        os.path.join(settings_folder, 'local_settings.py'), silent=False)
    CORS(app, resources={r"*": {"origins": "*"}})

    # DB
    db.init_app(app)

    # Signer/Verifier
    sv.config(pub_key_path=os.path.join(settings_folder, 'keypub'))

    # API
    api.init_app(app)
    app.register_blueprint(apidoc.apidoc)
    api.app = app

    # Mail
    api.mail = Mail(app)

    api.urltoken = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    return app
