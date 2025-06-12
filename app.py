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
import requests # Import library requests

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_fallback_key_dont_use_in_prod")

# --- Konfigurasi Imgur ---
# Dapatkan Client ID dari Imgur Anda dan simpan di .env
# PASTIKAN ANDA SUDAH MENAMBAHKAN IMGUR_CLIENT_ID="YOUR_CLIENT_ID" DI FILE .env ANDA
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID")
IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"
IMGUR_DELETE_URL_BASE = "https://api.imgur.com/3/image/" # Base URL untuk delete API

# Hapus atau komentar baris ini jika Anda sepenuhnya beralih ke Imgur.
# Jika ada postingan lama yang masih menggunakan gambar lokal, baris ini bisa tetap ada
# tetapi Anda harus mengelola penghapusan file lokal secara manual jika perlu.
UPLOAD_FOLDER = 'static/uploads'
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER # Tidak lagi diperlukan jika hanya pakai Imgur

# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)

# Konfigurasi MongoDB
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.myblogdb
posts_collection = db.posts
users_collection = db.users

# --- FUNGSI HELPER ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
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
    category = request.args.get('category', None) 
    
    posts_per_page = 6

    search_filter = {}
    if query:
        search_filter["$or"] = [
            {"title": {"$regex": query, "$options": "i"}},
            {"content": {"$regex": query, "$options": "i"}}
        ]
    
    if category:
        search_filter["categories"] = category
    
    total_posts = posts_collection.count_documents(search_filter)
    total_pages = math.ceil(total_posts / posts_per_page)
    skip = (page - 1) * posts_per_page
    
    all_posts = list(posts_collection.find(search_filter)
                                      .sort("created_at", -1)
                                      .skip(skip)
                                      .limit(posts_per_page))
    
    all_categories = posts_collection.distinct("categories")
    
    return render_template('index.html', 
                           posts=all_posts, 
                           query=query,
                           page=page,
                           total_pages=total_pages,
                           total_posts=total_posts,
                           all_categories=all_categories,
                           selected_category=category
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
        
        categories_input = request.form.get('categories')
        categories = [cat.strip() for cat in categories_input.split(',') if cat.strip()] if categories_input else []
        
        image_data = None # Ini akan menyimpan URL dan deletehash dari Imgur

        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                if file and allowed_file(file.filename):
                    headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
                    files = {'image': file.read()} # Imgur API mengharapkan 'image' sebagai bytes
                    
                    try:
                        response = requests.post(IMGUR_UPLOAD_URL, headers=headers, files=files)
                        response.raise_for_status() # Akan memunculkan HTTPError jika status code 4xx/5xx
                        
                        imgur_response_data = response.json()
                        if imgur_response_data['success']:
                            image_data = {
                                "url": imgur_response_data['data']['link'],
                                "deletehash": imgur_response_data['data']['deletehash']
                            }
                            flash('Gambar berhasil diunggah ke Imgur!', 'success')
                        else:
                            flash(f"Gagal mengunggah gambar ke Imgur: {imgur_response_data.get('data', {}).get('error', 'Kesalahan tidak diketahui')}", 'danger')
                            return render_template('new_post.html', title=title, content=content, author=author, categories=categories_input)
                    except requests.exceptions.RequestException as e:
                        flash(f'Terjadi kesalahan saat menghubungi Imgur API: {e}', 'danger')
                        return render_template('new_post.html', title=title, content=content, author=author, categories=categories_input)
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
            "image": image_data, # Simpan objek {url, deletehash}
            "categories": categories
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
        
        categories_input = request.form.get('categories')
        categories = [cat.strip() for cat in categories_input.split(',') if cat.strip()] if categories_input else []

        current_image_data = post.get('image') # Bisa string (lama) atau dict (baru) atau None
        new_image_data = current_image_data # Default, jika tidak ada gambar baru diunggah

        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                if file and allowed_file(file.filename):
                    # Hapus gambar lama dari Imgur jika ada deletehash
                    # Cek apakah current_image_data adalah dict dan punya deletehash
                    if isinstance(current_image_data, dict) and current_image_data.get('deletehash'):
                        deletehash = current_image_data['deletehash']
                        delete_url = f"{IMGUR_DELETE_URL_BASE}{deletehash}"
                        headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
                        try:
                            delete_response = requests.delete(delete_url, headers=headers)
                            delete_response.raise_for_status()
                            if delete_response.json().get('success'):
                                flash('Gambar lama berhasil dihapus dari Imgur!', 'info')
                            else:
                                flash(f"Gagal menghapus gambar lama dari Imgur: {delete_response.json().get('data', {}).get('error', 'Kesalahan tidak diketahui')}", 'warning')
                        except requests.exceptions.RequestException as e:
                            flash(f'Terjadi kesalahan saat menghubungi Imgur API untuk penghapusan: {e}', 'warning')
                    elif isinstance(current_image_data, str) and os.path.exists(os.path.join(UPLOAD_FOLDER, current_image_data)):
                         # Jika gambar lama adalah string (file lokal), hapus dari lokal
                         # Pastikan UPLOAD_FOLDER diatur dengan benar atau dihapus jika tidak diperlukan
                         try:
                             os.remove(os.path.join(UPLOAD_FOLDER, current_image_data))
                             flash('Gambar lokal lama berhasil dihapus.', 'info')
                         except OSError as e:
                             flash(f'Gagal menghapus gambar lokal lama: {e}', 'warning')
                    
                    # Unggah gambar baru ke Imgur
                    headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
                    files = {'image': file.read()}
                    try:
                        response = requests.post(IMGUR_UPLOAD_URL, headers=headers, files=files)
                        response.raise_for_status()
                        imgur_response_data = response.json()
                        if imgur_response_data['success']:
                            new_image_data = {
                                "url": imgur_response_data['data']['link'],
                                "deletehash": imgur_response_data['data']['deletehash']
                            }
                            flash('Gambar baru berhasil diunggah ke Imgur!', 'success')
                        else:
                            flash(f"Gagal mengunggah gambar baru ke Imgur: {imgur_response_data.get('data', {}).get('error', 'Kesalahan tidak diketahui')}", 'danger')
                            return render_template('edit_post.html', post=post, categories=categories_input)
                    except requests.exceptions.RequestException as e:
                        flash(f'Terjadi kesalahan saat menghubungi Imgur API untuk unggah: {e}', 'danger')
                        return render_template('edit_post.html', post=post, categories=categories_input)
                else:
                    flash('Format gambar tidak diizinkan. Gunakan PNG, JPG, JPEG, atau GIF.', 'warning')
                    return render_template('edit_post.html', post=post, categories=categories_input)
            elif file.filename == '' and 'clear_image' in request.form: # Jika checkbox "Hapus gambar ini" dicentang
                if isinstance(current_image_data, dict) and current_image_data.get('deletehash'):
                    deletehash = current_image_data['deletehash']
                    delete_url = f"{IMGUR_DELETE_URL_BASE}{deletehash}"
                    headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
                    try:
                        delete_response = requests.delete(delete_url, headers=headers)
                        delete_response.raise_for_status()
                        if delete_response.json().get('success'):
                            flash('Gambar berhasil dihapus dari Imgur!', 'info')
                            new_image_data = None # Set ke None karena gambar dihapus
                        else:
                            flash(f"Gagal menghapus gambar dari Imgur: {delete_response.json().get('data', {}).get('error', 'Kesalahan tidak diketahui')}", 'warning')
                    except requests.exceptions.RequestException as e:
                        flash(f'Terjadi kesalahan saat menghapus gambar dari Imgur API: {e}', 'warning')
                elif isinstance(current_image_data, str) and os.path.exists(os.path.join(UPLOAD_FOLDER, current_image_data)):
                    # Jika gambar lama adalah string (lokal) dan ingin dihapus
                    try:
                        os.remove(os.path.join(UPLOAD_FOLDER, current_image_data))
                        flash('Gambar lokal berhasil dihapus.', 'info')
                        new_image_data = None # Set ke None
                    except OSError as e:
                        flash(f'Gagal menghapus gambar lokal: {e}', 'warning')
                else:
                    flash('Gambar tidak dapat dihapus. Mungkin bukan unggahan Imgur atau tidak memiliki deletehash.', 'warning')
                    new_image_data = None # Tetap set ke None jika pengguna memilih hapus
        
        # Jika tidak ada file baru diunggah dan 'clear_image' tidak dicentang,
        # maka new_image_data tetap sama dengan current_image_data
        # Jika file diunggah atau 'clear_image' dicentang, new_image_data sudah diupdate
        # Tidak perlu ada else di sini

        if not title or not content or not author:
            flash('Semua kolom Judul, Konten, dan Penulis harus diisi!', 'danger')
            # Pertahankan data gambar yang ada jika validasi gagal
            return render_template('edit_post.html', post=post, categories=categories_input)


        posts_collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": {"title": title, "content": content, "author": author, "image": new_image_data, "categories": categories}}
        )
        flash('Postingan berhasil diperbarui!', 'success')
        return redirect(url_for('post_detail', id=id))
    
    post_categories_str = ", ".join(post.get('categories', []))
    return render_template('edit_post.html', post=post, categories=post_categories_str)

@app.route('/delete_post/<id>', methods=['POST'])
@login_required
def delete_post(id):
    post = posts_collection.find_one({"_id": ObjectId(id)})
    if post:
        image_data_to_delete = post.get('image') # Bisa string (lama) atau dict (baru) atau None
        
        # Periksa apakah gambar yang akan dihapus adalah dictionary dari Imgur dan memiliki deletehash
        if isinstance(image_data_to_delete, dict) and image_data_to_delete.get('deletehash'):
            deletehash = image_data_to_delete['deletehash']
            delete_url = f"{IMGUR_DELETE_URL_BASE}{deletehash}"
            headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
            try:
                delete_response = requests.delete(delete_url, headers=headers)
                delete_response.raise_for_status()
                if delete_response.json().get('success'):
                    flash('Gambar berhasil dihapus dari Imgur!', 'info')
                else:
                    flash(f"Gagal menghapus gambar dari Imgur: {delete_response.json().get('data', {}).get('error', 'Kesalahan tidak diketahui')}", 'warning')
            except requests.exceptions.RequestException as e:
                flash(f'Terjadi kesalahan saat menghapus gambar dari Imgur API: {e}', 'warning')
        elif isinstance(image_data_to_delete, str) and os.path.exists(os.path.join(UPLOAD_FOLDER, image_data_to_delete)):
            # Jika ada gambar tapi formatnya string (lokal) dan file ada, hapus dari lokal
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, image_data_to_delete))
                flash('Gambar lokal terkait berhasil dihapus.', 'info')
            except OSError as e:
                flash(f'Gagal menghapus gambar lokal: {e}', 'warning')
        
        result = posts_collection.delete_one({"_id": ObjectId(id)})
        if result.deleted_count == 1:
            flash('Postingan berhasil dihapus!', 'success')
        else:
            flash('Postingan tidak ditemukan atau gagal dihapus.', 'danger')
    else:
        flash('Postingan tidak ditemukan.', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main_`':
    app.run(debug=True)