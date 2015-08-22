#!/usr/bin/env python
# coding: utf-8

from datetime import datetime

from flask import url_for
from sqlalchemy.orm.exc import NoResultFound
from flask.ext.restplus import Resource, Api, apidoc
from flask.ext.mail import Message
from itsdangerous import BadSignature, SignatureExpired

from viralata.utils import decode_token

from models import Comment, Thread, Author
from extensions import db, sv


api = Api(version='1.0',
          title='Tagarela!',
          description='A commenting microservice. All non-get operations '
          'require a micro token.')

parser = api.parser()
parser.add_argument('token', location='json', help='TOKEN!!')
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


@api.route('/thread/<string:thread_name>/<int:comment_id>/report')
class ReportComment(Resource):

    def post(self, thread_name, comment_id):
        '''Report comment for possible delete.
        An e-mail will be sent to admins with a link to delete the comment.'''
        comment = get_comment(comment_id)
        token = api.urltoken.dumps((comment.id, comment.thread.name))
        suburl = api.url_for(DeleteReportedComment, token=token)
        delete_link = api.app.config['HOSTED_ADDRESS'] + suburl
        msg = Message(
                'Request to delete comment: %s' % comment.id,
                sender=api.app.config['SENDER_NAME'],
                recipients=api.app.config['ADMIN_EMAILS'])
        msg.body = api.app.config['EMAIL_TEMPLATE'].format(
            delete_link=delete_link,
            id=comment.id,
            author=comment.author.name,
            thread=comment.thread.name,
            created=comment.created,
            modified=comment.modified,
            text=comment.text,
        )
        api.mail.send(msg)
        return {'message': 'Reported!'}


@api.route('/delete_reported/<string:token>')
class DeleteReportedComment(Resource):

    def get(self, token):
        '''Delete a reported comment from a thread using a special token.'''
        try:
            comment_id, thread_name = api.urltoken.loads(
                token,
                max_age=api.app.config['MAX_AGE_REPORT_TOKENS']
            )
        except BadSignature:
            api.abort(400, 'Bad Signature')
        except SignatureExpired:
            api.abort(400, 'Signature Expired')
        comment = get_comment(comment_id)
        if comment.thread.name != thread_name:
            api.abort(400, 'Thread name mismatch')
        db.session.delete(comment)
        db.session.commit()
        return {'message': 'Deleted!'}


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


def get_comment(comment_id):
    try:
        return db.session.query(Comment).filter_by(id=comment_id).one()
    except NoResultFound:
        api.abort(404, 'Comment not found')


def check_comment_author(comment_id, author_name):
    '''Checks if comment_id exists and author_name is its author.
    Returns the comment.'''
    comment = get_comment(comment_id)

    if comment.author.name != author_name:
        api.abort(400, 'You seem not to be the author of this comment...')

    return comment
