#!/usr/bin/env python
# coding: utf-8

from __future__ import unicode_literals  # unicode by default

# import pytz
import arrow
import bleach
from sqlalchemy import desc
from sqlalchemy.orm.exc import NoResultFound
from flask.ext.restplus import Resource
from flask.ext.mail import Message
from itsdangerous import BadSignature, SignatureExpired

from viralata.utils import decode_token
from cutils import date_to_json, paginate, ExtraApi

from models import Comment, Thread, Author
from extensions import db, sv


api = ExtraApi(version='1.0',
               title='Tagarela!',
               description='A commenting microservice. All non-get operations '
               'require a micro token.')

api.update_parser_arguments({
    'text': {
        'location': 'json',
        'help': 'The text for the comment.',
    },
    'vote': {
        'location': 'json',
        'type': bool,
        'help': 'Use "true" for a upvote, "false" for a downvote.',
    },
})


@api.route('/thread/<string:thread_name>')
class ThreadAPI(Resource):

    def get(self, thread_name):
        '''Get comments from a thread.'''
        return get_thread_comments(thread_name=thread_name)

    @api.doc(parser=api.create_parser('token', 'text'))
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

        now = arrow.utcnow()
        comment = Comment(author_id=author_id, text=text, thread_id=thread.id,
                          created=now, modified=now)
        db.session.add(comment)
        db.session.commit()
        return get_thread_comments(thread)


@api.route('/comment')
class ListCommentsAPI(Resource):

    @api.doc(parser=api.create_parser('page', 'per_page_num'))
    def get(self):
        '''List comments by decrescent creation time.'''
        args = api.general_parse()
        page = args['page']
        per_page_num = args['per_page_num']
        comments = (db.session.query(Comment, Thread.name)
                    .filter(Comment.thread_id == Thread.id)
                    .order_by(desc(Comment.created))
                    .filter_by(hidden=False))
        # Limit que number of results per page
        comments, total = paginate(comments, page, per_page_num)
        return {
            'comments': [
                {
                    'thread_name': thread_name,
                    'id': c.id,
                    'text': c.text,
                    'author': c.author.name,
                    'created': date_to_json(c.created),
                    'modified': date_to_json(c.modified),
                    # 'url': api.url_for(CommentAPI, comment_id=c.id),
                } for c, thread_name in comments],
            'total': total,
        }


@api.route('/comment/<int:comment_id>')
class CommentAPI(Resource):

    @api.doc(parser=api.create_parser('token', 'text'))
    def post(self, comment_id):
        '''Add a comment reply to this comment.'''
        args, author_name = parse_and_decode()

        text = bleach.clean(args['text'], strip=True)

        parent = get_comment(comment_id)
        author_id = get_author_add_if_needed(author_name)

        now = arrow.utcnow()
        comment = Comment(author_id=author_id, text=text,
                          thread_id=parent.thread_id,
                          created=now, modified=now,
                          parent_id=parent.id)
        db.session.add(comment)
        db.session.commit()
        return get_thread_comments(comment.thread)

    @api.doc(parser=api.create_parser('token'))
    def delete(self, comment_id):
        '''Delete a comment from a thread. Returns thread.'''
        args, author_name = parse_and_decode()
        comment = check_comment_author(comment_id, author_name)
        thread = comment.thread
        delete_comment(comment)
        return get_thread_comments(thread)

    @api.doc(parser=api.create_parser('token', 'text'))
    def put(self, comment_id):
        '''Edit a comment in a thread.'''
        args, author_name = parse_and_decode()
        comment = check_comment_author(comment_id, author_name)
        comment.text = args['text']
        comment.modified = arrow.utcnow()
        db.session.commit()
        return get_thread_comments(comment.thread)


@api.route('/vote/<int:comment_id>')
class VoteAPI(Resource):

    @api.doc(parser=api.create_parser('token', 'vote'))
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
        'created': date_to_json(c.created),
        'modified': date_to_json(c.modified),
        'upvotes': c.likes,
        'downvotes': c.dislikes,
        'hidden': c.hidden,
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
            comments = []
            count = 0
            # api.abort(404)

    if thread:
        comments = [comment_to_dict(c) for c in thread.comments
                    if c.parent_id is None]
        thread_name = thread.name
        count = len(thread.comments)

    return {
        'comments': comments,
        'name': thread_name,
        'count': count
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
    '''Return args and username'''
    args = api.general_parse()
    return args, decode_token(args['token'], sv, api)['username']


def delete_comment(comment):
    # If the comment has children, hide instead of deleting.
    # (you wouldn't delete a comment with children, would you?)
    if comment.children:
        comment.hidden = True
        comment.modified = arrow.utcnow()
    else:
        db.session.delete(comment)
        # Remove hidden ancestors (this avoids leaving chidrenless comments
        # hidden)
        parent = comment.parent
        if parent and parent.hidden:
            delete_comment(parent)
    db.session.commit()
