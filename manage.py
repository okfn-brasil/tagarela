#!/usr/bin/env python
# coding: utf-8

import os

from flask.ext.script import Server, Manager, Shell

from tagarela.app import create_app
from tagarela.extensions import db


manager = Manager(create_app)

manager.add_option(
    "-s", "--settings", dest="settings_folder", required=False,
    default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'settings'))

manager.add_command('run', Server(port=5003))
manager.add_command('shell', Shell(make_context=lambda: {
    'app': manager.app,
    'db': db,
}))


@manager.command
def initdb():
    db.drop_all()
    db.create_all()

if __name__ == '__main__':
    manager.run()
