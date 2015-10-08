# coding: utf-8

import os


virtenv = os.environ['OPENSHIFT_PYTHON_DIR'] + '/virtenv/'
virtualenv = os.path.join(virtenv, 'bin/activate_this.py')
try:
    execfile(virtualenv, dict(__file__=virtualenv))
except IOError:
    pass

from tagarela.app import create_app
application = create_app(os.environ['OPENSHIFT_DATA_DIR'])
