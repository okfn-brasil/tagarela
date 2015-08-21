#!/usr/bin/env python
# coding: utf-8

from datetime import datetime

from sqlalchemy.orm.exc import NoResultFound
from flask.ext.restplus import Resource, Api, apidoc

from viralata.utils import decode_token

from models import Comment, Thread, Author
from extensions import db, sv


api = Api(version='1.0',
          title='Tagarela!',
          description='A commenting microservice. All non-get operations '
          'require a micro token.')

parser = api.parser()
parser.add_argument('token', location='json', help='The task details')
parser.add_argument('text', location='json')


@api.route('/thread/<string:thread_name>/add')
class AddComment(Resource):

    @api.doc(parser=parser)
    def post(self, thread_name):
        '''Add a comment to thread.'''
        args = parser.parse_args()
        decoded = decode_token(args['token'], sv, api)
        author_name = decoded['username']

        text = args['text']

        # Get thread (add if needed)
        try:
            thread_id = (db.session.query(Thread.id)
                         .filter(Thread.name == thread_name).one())
        except NoResultFound:
            thread = Thread(name=thread_name)
            db.session.add(thread)
            db.session.commit()
            thread_id = thread.id

        # Get author (add if needed)
        try:
            author_id = (db.session.query(Author.id)
                         .filter(Author.name == author_name).one())
        except NoResultFound:
            author = Author(name=author_name)
            db.session.add(author)
            db.session.commit()
            author_id = author.id

        now = datetime.now()
        comment = Comment(author_id=author_id, text=text, thread_id=thread_id,
                          created=now, modified=now)
        db.session.add(comment)
        db.session.commit()
        return get_thread_comments(thread_name)


@api.route('/thread/<string:thread_name>/<int:comment_id>/delete')
class DeleteComment(Resource):

    def delete(self, thread_name, comment_id):
        '''Delete a comment from a thread. Returns thread.'''
        args = parser.parse_args()
        decoded = decode_token(args['token'], sv, api)
        comment = check_comment_author(comment_id, decoded['username'])
        db.session.delete(comment)
        db.session.commit()
        return get_thread_comments(thread_name)


@api.route('/thread/<string:thread_name>/<int:comment_id>/edit')
class EditComment(Resource):

    def put(self, thread_name, comment_id):
        '''Edit a comment in a thread.'''
        args = parser.parse_args()
        decoded = decode_token(args['token'], sv, api)
        comment = check_comment_author(comment_id, decoded['username'])
        comment.text = args['text']
        db.session.commit()
        return get_thread_comments(thread_name)


@api.route('/thread/<string:thread_name>')
class GetThread(Resource):

    def get(self, thread_name):
        '''Get comments from a thread.'''
        return get_thread_comments(thread_name)


def get_thread_comments(thread_name):
    try:
        thread = (db.session.query(Thread)
                    .filter(Thread.name == thread_name).one())
    except NoResultFound:
        return {'comments': []}
        # api.abort(404)
    return {
        'comments': [
            {
                'id': c.id,
                'text': c.text,
                'author': c.author.name,
                'created': str(c.created),
                'modified': str(c.modified),
            }
            for c in thread.comments
        ]
    }


def check_comment_author(comment_id, author_name):
    '''Checks if comment_id exists and author_name is its author.
    Returns the comment.'''
    try:
        comment = db.session.query(Comment).filter_by(id=comment_id).one()
    except NoResultFound:
        api.abort(404, 'Comment not found')

    if comment.author.name != author_name:
        api.abort(400, 'You seem not to be the author of this comment...')

    return comment
