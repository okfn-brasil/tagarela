#!/usr/bin/env python
# coding: utf-8

from flask.ext.sqlalchemy import SQLAlchemy

from viratoken import SignerVerifier


db = SQLAlchemy()
sv = SignerVerifier()
