# 📄 main.py (VERSI BARU DENGAN ADMIN LOGIN & SESSIONS)

from fastapi import File, UploadFile 
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Query
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import os 
import shutil 
import sqlite3
import urllib.parse 

app = FastAPI()

# --- Configuration Middleware ---
# Tambahkan Session Middleware untuk mengelola status login & keranjang
app.add_middleware(SessionMiddleware, secret_key="kunci-rahasia-admin") 

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Database Connection and Functions ---

def get_db_connection():
    """Membuat koneksi ke database dengan sqlite3.Row untuk hasil dict-like"""
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row 
    return conn

def get_products():
    """Mengambil semua produk dari database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, category, image FROM products") 
    data = cursor.fetchall()
    conn.close()
    return data

# --- Fungsi Utility Keranjang ---

def get_cart_data(request: Request):
    """Mengambil data keranjang dari session dan menghitung total harga/count"""
    # Menggunakan dict untuk keranjang agar bisa diakses per product_id
    cart_items = request.session.get("cart_items", {}) 
    
    # Konversi dictionary ke list untuk ditampilkan di Jinja2
    cart_list = []
    for product_id, item_data in cart_items.items():
        # Tambahkan ID produk ke setiap item dalam list
        item_data['id'] = product_id # Penting untuk tombol hapus
        cart_list.append(item_data)

    total_price = sum(item['price'] * item['qty'] for item in cart_list)
    total_count = sum(item['qty'] for item in cart_list)
    
    return cart_list, total_price, total_count

# --- Admin Credentials (Sederhana) ---
ADMIN_CODE = "200820"

# --- Route Login ---
@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    _, _, cart_count = get_cart_data(request) # Ambil data keranjang dari session
    
    if request.session.get("logged_in"):
        return RedirectResponse(url="/admin", status_code=302)
        
    return templates.TemplateResponse("login.html", { 
        "request": request,
        "title": "Admin Login",
        "cart_count": cart_count
    })

@app.post("/login")
async def login_submit(request: Request, admin_code: str = Form(...)): 
    
    if admin_code == ADMIN_CODE: 
        request.session["logged_in"] = True
        return RedirectResponse(url="/admin", status_code=303)
    else:
        _, _, cart_count = get_cart_data(request)
        return templates.TemplateResponse("login.html", { 
            "request": request, 
            "title": "Admin Login",
            "error": "Kode admin salah.", 
            "cart_count": cart_count
        }, status_code=401)

@app.get("/logout")
def logout(request: Request):
    """Menghapus sesi login"""
    request.session.pop("logged_in", None)
    return RedirectResponse(url="/", status_code=303)

# --- Route Halaman Admin ---
@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    """Menampilkan dashboard admin dan daftar produk"""
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
        
    products = get_products()
    
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "title": "Dashboard Admin",
        "products": products
    })

# Pastikan fungsi ini ada di main.py Anda!
@app.get("/admin/tambah_produk", response_class=HTMLResponse)
def add_product_form(request: Request):
    """Menampilkan form tambah produk"""
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
        
    return templates.TemplateResponse("tambah_produk.html", {
        "request": request,
        "title": "Tambah Produk Baru"
    })

# --- Route Tambah Produk (POST) ---
@app.post("/admin/tambah_produk")
def add_product_submit(
    request: Request,
    name: str = Form(...),
    price: int = Form(...),
    category: str = Form(...),
    image_file: UploadFile = File(...) 
):
    """Memproses form tambah produk, menyimpan file, dan memasukkan ke database"""
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=403, detail="Akses ditolak")
        
    file_location = f"static/images/{image_file.filename}"
    
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan file: {e}")
    
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO products (name, price, category, image) VALUES (?, ?, ?, ?)",
            (name, price, category, image_file.filename)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Gagal menambahkan produk ke DB: {e}")
    
    conn.close()
    return RedirectResponse(url="/admin", status_code=303)

# --- Route Edit Produk (GET) ---
@app.get("/admin/edit/{product_id}", response_class=HTMLResponse)
def edit_product_form(request: Request, product_id: int):
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
    
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    
    if product is None:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
        
    return templates.TemplateResponse("edit_produk.html", {
        "request": request,
        "title": f"Edit Produk: {product['name']}",
        "product": product
    })

# --- Route Edit Produk (POST) ---
@app.post("/admin/edit/{product_id}")
def edit_product_submit(
    request: Request,
    product_id: int,
    name: str = Form(...),
    price: int = Form(...),
    category: str = Form(...),
    image_file: UploadFile = File(None) 
):
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=403, detail="Akses ditolak")
        
    conn = get_db_connection()
    current_product = conn.execute("SELECT image FROM products WHERE id = ?", (product_id,)).fetchone()
    
    if current_product is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
        
    image_filename = current_product['image']
    
    if image_file and image_file.filename:
        image_filename = image_file.filename
        file_location = f"static/images/{image_filename}"
        
        try:
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(image_file.file, buffer)
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan file: {e}")
            
    try:
        conn.execute(
            "UPDATE products SET name = ?, price = ?, category = ?, image = ? WHERE id = ?",
            (name, price, category, image_filename, product_id)
        )
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Gagal memperbarui produk: {e}")
    
    conn.close()
    return RedirectResponse(url="/admin", status_code=303)

# --- Route Hapus Produk (GET) ---
@app.get("/admin/hapus/{product_id}")
def delete_product(request: Request, product_id: int):
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
        
    conn = get_db_connection()
    
    try:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Gagal menghapus produk: {e}")

    conn.close()
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/search", response_class=HTMLResponse)
async def search_products(request: Request, q: str = Query(None)):
    
    conn = get_db_connection()
    products = []
    search_query = ""
    _, _, cart_count = get_cart_data(request)
    
    if q:
        search_term = q.strip()
        search_query = search_term
        
        products = conn.execute(
            'SELECT * FROM products WHERE name LIKE ? OR category LIKE ?', 
            ('%' + search_term + '%', '%' + search_term + '%')
        ).fetchall()
        
    conn.close()
    
    return templates.TemplateResponse("product_list.html", {
        "request": request,
        "title": f"Hasil Pencarian: {search_query}",
        "products": products,
        "search_query": search_query,
        "cart_count": cart_count
    })

# --- ROUTE UTAMA LAINNYA ---

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    products = get_products()
    _, _, cart_count = get_cart_data(request)
    return templates.TemplateResponse("index.html", { 
        "request": request,
        "products": products,
        "title": "Beranda",
        "cart_count": cart_count
    })

@app.get("/produk", response_class=HTMLResponse)
def product_list(request: Request):
    products = get_products()
    _, _, cart_count = get_cart_data(request)
    return templates.TemplateResponse("product_list.html", { 
        "request": request,
        "products": products,
        "title": "Semua Produk",
        "cart_count": cart_count
    })

# --- MENGHAPUS GLOBAL CART & MENGGUNAKAN SESSION ---

@app.post("/tambah_keranjang/{product_id}")
def add_to_cart(product_id: int, request: Request):
    
    # 1. Ambil keranjang dari session
    cart_items = request.session.get("cart_items", {}) 
    
    conn = get_db_connection()
    # Mengambil product.id sebagai string untuk konsistensi session key
    product = conn.execute("SELECT id, name, price FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()

    if product:
        product_dict = dict(product) 
        # ID produk harus diubah menjadi string karena key session hanya menerima string/int, 
        # tetapi konsistensi akan lebih mudah jika kita menggunakan string untuk dictionary key
        product_key = str(product_id) 
        
        if product_key in cart_items:
            # Jika sudah ada, tambah kuantitas
            cart_items[product_key]['qty'] += 1
        else:
            # Jika baru, tambahkan item baru
            cart_items[product_key] = {'name': product_dict['name'], 'price': product_dict['price'], 'qty': 1}
        
        # 2. Simpan kembali keranjang ke session
        request.session["cart_items"] = cart_items
    
    # Redirect ke halaman produk/index agar user bisa lanjut belanja
    # Perhatikan: Karena Anda mematikan JS, ini akan menyebabkan reload. 
    # Jika dipanggil dari tombol di index.html, user kembali ke index.
    return RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)

@app.post("/hapus_keranjang/{product_id}")
async def hapus_keranjang(product_id: int, request: Request):
    """
    Menghapus item produk dari keranjang belanja (session) TANPA JS.
    Dipicu oleh form POST dari keranjang.html.
    """
    product_key = str(product_id)
    cart_items = request.session.get("cart_items", {})

    if product_key in cart_items:
        # Hapus item dari dictionary
        cart_items.pop(product_key)
        
        # Simpan kembali keranjang ke session
        request.session["cart_items"] = cart_items
        
    # Redirect kembali ke halaman keranjang
    return RedirectResponse(url="/keranjang", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/keranjang", response_class=HTMLResponse)
def view_cart(request: Request):
    
    cart_items, total_price, cart_count = get_cart_data(request)
    
    return templates.TemplateResponse("keranjang.html", {
        "request": request,
        "cart": cart_items, # Berisi list item, termasuk ID
        "total_price": total_price,
        "title": "Keranjang Belanja",
        "cart_count": cart_count
    })

@app.get("/checkout")
def checkout(request: Request):
    
    cart_items, total_price, _ = get_cart_data(request)
    
    if not cart_items:
        return RedirectResponse(url="/keranjang", status_code=302)

    whatsapp_number = "6287769390475" 
    
    pesanan_list = []
    
    for item in cart_items: 
        subtotal = item['price'] * item['qty']
        formatted_price = "{:,.0f}".format(subtotal).replace(",", ".") 
        pesanan_list.append(f"- {item['qty']}x {item['name']} (Rp{formatted_price})")
    
    pesanan_text = "\n".join(pesanan_list)
    
    message = (
        f"*PESANAN AKSESORI BARU*\n\n"
        f"Detail Pesanan:\n"
        f"{pesanan_text}\n\n"
        f"*Total Harga:* Rp{'{:,.0f}'.format(total_price).replace(',', '.')}\n\n"
        f"Mohon konfirmasi pesanan ini. Terima kasih!"
    )
    
    whatsapp_url = f"https://wa.me/{whatsapp_number}?text={urllib.parse.quote(message)}"
    
    # KOSONGKAN KERANJANG SETELAH CHECKOUT
    if "cart_items" in request.session:
        del request.session["cart_items"]
    
    return RedirectResponse(url=whatsapp_url, status_code=303)