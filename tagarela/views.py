#!/usr/bin/env python
# coding: utf-8

from datetime import datetime
# from collections import OrderedDict

import bleach
from sqlalchemy.orm.exc import NoResultFound
from flask.ext.restplus import Resource, Api
from flask.ext.mail import Message
from itsdangerous import BadSignature, SignatureExpired

from viralata.utils import decode_token

from models import Comment, Thread, Author
from extensions import db, sv


api = Api(version='1.0',
          title='Tagarela!',
          description='A commenting microservice. All non-get operations '
          'require a micro token.')

arguments = {
    'token': {
        'location': 'json',
        'help': 'The authentication token.',
    },
    'text': {
        'location': 'json',
        'help': 'The text for the comment.',
    },
    'vote': {
        'location': 'json',
        'type': bool,
        'help': 'Use "true" for a upvote, "false" for a downvote.',
    }
}


def create_parser(*args):
    '''Create a parser for the passed arguments.'''
    parser = api.parser()
    for arg in args:
        parser.add_argument(arg, **arguments[arg])
    return parser


general_parser = create_parser(*arguments)


@api.route('/thread/<string:thread_name>')
class ThreadAPI(Resource):

    def get(self, thread_name):
        '''Get comments from a thread.'''
        print("____________________________________________________")
        # thread = (db.session.query(Thread).filter(Thread.name == thread_name).one())
        print("........................")
        # return {}
        return get_thread_comments(thread_name=thread_name)

    @api.doc(parser=create_parser('token', 'text'))
    def post(self, thread_name):
        '''Add a comment to thread.'''
        args, author_name = parse_and_decode()

        text = bleach.clean(args['text'], strip=True)

        # Get thread (add if needed)
        try:
            thread = (db.session.query(Thread)
                      .filter(Thread.name == thread_name).one())
        except NoResultFound:
            thread = Thread(name=thread_name)
            db.session.add(thread)
            db.session.commit()

        author_id = get_author_add_if_needed(author_name)

        now = datetime.now()
        comment = Comment(author_id=author_id, text=text, thread_id=thread.id,
                          created=now, modified=now)
        db.session.add(comment)
        db.session.commit()
        return get_thread_comments(thread)


@api.route('/comment/<int:comment_id>')
class CommentAPI(Resource):

    @api.doc(parser=create_parser('token', 'text'))
    def post(self, comment_id):
        '''Add a comment reply to this comment.'''
        args, author_name = parse_and_decode()

        text = bleach.clean(args['text'], strip=True)

        parent = get_comment(comment_id)
        author_id = get_author_add_if_needed(author_name)

        now = datetime.now()
        comment = Comment(author_id=author_id, text=text,
                          thread_id=parent.thread_id,
                          created=now, modified=now,
                          parent_id=parent.id)
        db.session.add(comment)
        db.session.commit()
        return get_thread_comments(comment.thread)

    @api.doc(parser=create_parser('token'))
    def delete(self, comment_id):
        '''Delete a comment from a thread. Returns thread.'''
        args, author_name = parse_and_decode()
        comment = check_comment_author(comment_id, author_name)
        thread = comment.thread
        delete_comment(comment)
        return get_thread_comments(thread)

    @api.doc(parser=create_parser('token', 'text'))
    def put(self, comment_id):
        '''Edit a comment in a thread.'''
        args, author_name = parse_and_decode()
        comment = check_comment_author(comment_id, author_name)
        comment.text = args['text']
        db.session.commit()
        return get_thread_comments(comment.thread)


@api.route('/vote/<int:comment_id>')
class VoteAPI(Resource):

    @api.doc(parser=create_parser('token', 'vote'))
    def post(self, comment_id):
        '''Like/dislike a comment in a thread.
        If vote is False, dislike; else like.'''
        args, author_name = parse_and_decode()
        vote = args['vote']
        author_id = get_author_add_if_needed(author_name)
        comment = get_comment(comment_id)
        if comment.author_id == author_id:
            api.abort(400, 'You cannot vote for your own comments...')
        comment.set_vote(author_id, vote)
        return get_thread_comments(comment.thread)


@api.route('/report/<int:comment_id>')
class ReportAPI(Resource):

    def post(self, comment_id):
        '''Report comment for possible delete.
        An e-mail will be sent to admins with a link to delete the comment.'''
        comment = get_comment(comment_id)
        token = api.urltoken.dumps((comment.id, comment.thread.name))
        suburl = api.url_for(DeleteReportedAPI, token=token)
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
class DeleteReportedAPI(Resource):

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
        delete_comment(comment)
        return {'message': 'Deleted!'}


def comment_to_dict(c):
    '''Return a comment as a dict (recursively including children).'''
    return {
        'id': c.id,
        'text': c.text,
        'author': c.author.name,
        'created': str(c.created),
        'modified': str(c.modified),
        'upvotes': c.likes,
        'downvotes': c.dislikes,
        'url': api.url_for(CommentAPI, comment_id=c.id),
        'vote_url': api.url_for(VoteAPI, comment_id=c.id),
        'report_url': api.url_for(ReportAPI, comment_id=c.id),
        'replies': [] if c.children is None else [
            comment_to_dict(child)
            for child in c.children
        ]
    }


def get_thread_comments(thread=None, thread_name=None):
    '''Return the comments of a thread.
    May receive a thread object or the name of a thread.'''
    if thread_name:
        try:
            thread = (db.session.query(Thread)
                      .filter(Thread.name == thread_name)
                      .options(db.joinedload('comments.author'),
                               db.joinedload('comments.children'))
                      .one())
        except NoResultFound:
            return {'comments': []}
            # api.abort(404)
    return {
        'comments': [
            comment_to_dict(c)
            for c in thread.comments if c.parent_id is None
        ]
    }


def get_comment(comment_id):
    '''Return a comment.'''
    try:
        return db.session.query(Comment).filter_by(id=comment_id).one()
    except NoResultFound:
        api.abort(404, 'Comment not found')


def get_author_add_if_needed(author_name):
    '''Get author id, adding if needed.'''
    try:
        author_id = (db.session.query(Author.id)
                     .filter(Author.name == author_name).one())
    except NoResultFound:
        author = Author(name=author_name)
        db.session.add(author)
        db.session.commit()
        author_id = author.id
    return author_id


def check_comment_author(comment_id, author_name):
    '''Checks if comment_id exists and author_name is its author.
    Returns the comment.'''
    comment = get_comment(comment_id)

    if comment.author.name != author_name:
        api.abort(400, 'You seem not to be the author of this comment...')

    return comment


def parse_and_decode():
    '''Return args and user name'''
    args = general_parser.parse_args()
    return args, decode_token(args['token'], sv, api)['username']


def delete_comment(comment):
    # TODO: tratar quando tem "filhos"
    db.session.delete(comment)
    db.session.commit()
