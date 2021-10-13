from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from werkzeug.utils import secure_filename

from app.auth import login_required
from app.db import get_db
import os
import boto3

def upload_file(file_name, bucket, object_name):
    s3_client = boto3.client('s3')
    response = s3_client.upload_file(file_name, bucket, object_name)
    return response

UPLOAD_FOLDER = 'uploads'
BUCKET = 'social-networking-test'

bp = Blueprint('post', __name__)

@bp.route('/')
def index():
    db = get_db()
    posts = db.execute(
        'SELECT p.id, img_url, created, author_id, username'
        ' FROM post p JOIN user u ON p.author_id = u.id'
        ' ORDER BY created DESC'
    ).fetchall()
    s3_client = boto3.client('s3')
    public_urls = []
    for post in posts:
        public_urls.append(s3_client.generate_presigned_url('get_object', Params = {'Bucket': BUCKET, 'Key': post['img_url']}, ExpiresIn = 100))
    return render_template('post/index.html', posts=posts, public_urls=public_urls)

@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        f = request.files['img']
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        f.save(os.path.join(UPLOAD_FOLDER, secure_filename(f.filename)))
        upload_file(f"{UPLOAD_FOLDER}/{f.filename}", BUCKET, f"{str(g.user['id'])}/{f.filename}")
        image_url = str(g.user['id']) + '/' + f.filename
        error = None

        if not image_url:
            error = 'Image is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO post (img_url, author_id)'
                ' VALUES (?, ?)',
                (image_url, g.user['id'])
            )
            db.commit()
            return redirect(url_for('post.index'))

    return render_template('post/create.html')

def get_post(id, check_author=True):
    post = get_db().execute(
        'SELECT p.id, img_url, created, author_id, username'
        ' FROM post p JOIN user u ON p.author_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    if check_author and post['author_id'] != g.user['id']:
        abort(403)

    return post

@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    post = get_post(id)

    if request.method == 'POST':
        f = request.files['img']
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        f.save(os.path.join(UPLOAD_FOLDER, secure_filename(f.filename)))
        upload_file(f"{UPLOAD_FOLDER}/{f.filename}", BUCKET, f"{str(g.user['id'])}/{f.filename}")
        image_url = str(g.user['id']) + '/' + f.filename
        error = None

        if not image_url:
            error = 'Image is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE post SET img_url = ?'
                ' WHERE id = ?',
                (image_url, id)
            )
            db.commit()
            return redirect(url_for('post.index'))

    return render_template('post/update.html', post=post)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_post(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('post.index'))