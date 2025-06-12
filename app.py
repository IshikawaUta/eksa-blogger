import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from uuid import uuid4
import math

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_fallback_key_dont_use_in_prod")

# Konfigurasi Upload Gambar
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Konfigurasi MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.myblogdb
posts_collection = db.posts
users_collection = db.users

# --- FUNGSI HELPER ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Anda harus login sebagai admin untuk mengakses halaman ini.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTE AUTENTIKASI ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = users_collection.find_one({"username": username})

        if user and check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['username'] = user['username']
            flash('Berhasil Login sebagai Admin!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Username atau password salah.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('Anda telah logout.', 'info')
    return redirect(url_for('index'))

# --- RUTE BLOG ---
@app.route('/')
def index():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', None) # Ambil parameter kategori
    
    posts_per_page = 6

    search_filter = {}
    if query:
        search_filter["$or"] = [
            {"title": {"$regex": query, "$options": "i"}},
            {"content": {"$regex": query, "$options": "i"}}
        ]
    
    if category: # Tambahkan filter kategori jika ada
        search_filter["categories"] = category
    
    total_posts = posts_collection.count_documents(search_filter)
    total_pages = math.ceil(total_posts / posts_per_page)
    skip = (page - 1) * posts_per_page
    
    all_posts = list(posts_collection.find(search_filter)
                                      .sort("created_at", -1)
                                      .skip(skip)
                                      .limit(posts_per_page))
    
    # Dapatkan semua kategori unik untuk ditampilkan di filter (opsional, bisa lebih efisien)
    # Ini mungkin berat jika jumlah postingan sangat banyak, pertimbangkan caching
    all_categories = posts_collection.distinct("categories")
    
    return render_template('index.html', 
                           posts=all_posts, 
                           query=query,
                           page=page,
                           total_pages=total_pages,
                           total_posts=total_posts,
                           all_categories=all_categories, # Kirim semua kategori
                           selected_category=category # Kirim kategori yang sedang aktif
                           )

@app.route('/post/<id>')
def post_detail(id):
    post = posts_collection.find_one({"_id": ObjectId(id)})
    if not post:
        flash('Postingan tidak ditemukan.', 'danger')
        return redirect(url_for('index'))
    return render_template('post.html', post=post)

@app.route('/new_post', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        author = request.form.get('author')
        
        # Tangani kategori/tag
        categories_input = request.form.get('categories')
        categories = [cat.strip() for cat in categories_input.split(',') if cat.strip()] if categories_input else []
        
        image_filename = None

        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                if file and allowed_file(file.filename):
                    original_filename = secure_filename(file.filename)
                    unique_filename = str(uuid4()) + "_" + original_filename
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(filepath)
                    image_filename = unique_filename
                else:
                    flash('Format gambar tidak diizinkan. Gunakan PNG, JPG, JPEG, atau GIF.', 'warning')
                    return render_template('new_post.html', title=title, content=content, author=author, categories=categories_input)

        if not title or not content or not author:
            flash('Semua kolom Judul, Konten, dan Penulis harus diisi!', 'danger')
            return render_template('new_post.html', title=title, content=content, author=author, categories=categories_input)

        new_post_data = {
            "title": title,
            "content": content,
            "author": author,
            "created_at": datetime.now(),
            "image": image_filename,
            "categories": categories # Simpan kategori
        }
        posts_collection.insert_one(new_post_data)
        flash('Postingan berhasil ditambahkan!', 'success')
        return redirect(url_for('index'))
    return render_template('new_post.html')

@app.route('/edit_post/<id>', methods=['GET', 'POST'])
@login_required
def edit_post(id):
    post = posts_collection.find_one({"_id": ObjectId(id)})
    if not post:
        flash('Postingan tidak ditemukan.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        author = request.form.get('author')
        
        # Tangani kategori/tag
        categories_input = request.form.get('categories')
        categories = [cat.strip() for cat in categories_input.split(',') if cat.strip()] if categories_input else []

        image_filename = post.get('image')
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                if file and allowed_file(file.filename):
                    if image_filename:
                        old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                        if os.path.exists(old_filepath):
                            os.remove(old_filepath)
                    
                    original_filename = secure_filename(file.filename)
                    unique_filename = str(uuid4()) + "_" + original_filename
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    file.save(filepath)
                    image_filename = unique_filename
                else:
                    flash('Format gambar tidak diizinkan. Gunakan PNG, JPG, JPEG, atau GIF.', 'warning')
                    return render_template('edit_post.html', post=post, categories=categories_input)

        if not title or not content or not author:
            flash('Semua kolom Judul, Konten, dan Penulis harus diisi!', 'danger')
            return render_template('edit_post.html', post=post, categories=categories_input)

        posts_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"title": title, "content": content, "author": author, "image": image_filename, "categories": categories}}
        )
        flash('Postingan berhasil diperbarui!', 'success')
        return redirect(url_for('post_detail', id=id))
    
    # Untuk GET request, pastikan kategori ditampilkan di form
    post_categories_str = ", ".join(post.get('categories', []))
    return render_template('edit_post.html', post=post, categories=post_categories_str)

@app.route('/delete_post/<id>', methods=['POST'])
@login_required
def delete_post(id):
    post = posts_collection.find_one({"_id": ObjectId(id)})
    if post:
        if post.get('image'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], post['image'])
            if os.path.exists(filepath):
                os.remove(filepath)
        
        result = posts_collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 1:
            flash('Postingan berhasil dihapus!', 'success')
        else:
            flash('Postingan tidak ditemukan atau gagal dihapus.', 'danger')
    else:
        flash('Postingan tidak ditemukan.', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)