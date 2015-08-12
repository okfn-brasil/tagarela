#!/usr/bin/env python
# coding: utf-8

from setuptools import setup

setup(
    name="tagarela",
    version='0.1',
    description='Microservice for comments.',
    author='Andrés M. R. Martano',
    author_email='andres@inventati.org',
    url='https://gitlab.com/ok-br/tagarela',
    packages=["tagarela"],
    install_requires=[
        'Flask',
        'Flask-Script',
        'Flask-Restplus',
        'Flask-CORS',
        'Flask-SQLAlchemy',
        'viratoken',
        # psycopg2, # for Postgres support
    ],
    keywords=['comments', 'microservice'],
    classifiers=[
        "Development Status :: 3 - Alpha"
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
        "Environment :: Web Environment",
        "Topic :: Internet :: WWW/HTTP"
        # "Topic :: Internet :: WWW/HTTP :: Session",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: Message Boards",
    ]
)
