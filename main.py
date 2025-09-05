import sqlite3
from fastapi import FastAPI, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime
import hashlib

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="a_very_secret_key_here")

templates = Jinja2Templates(directory="templates")
DATABASE = "bbs.db"
POSTS_PER_PAGE = 10

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, page: int = Query(1, ge=1)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    offset = (page - 1) * POSTS_PER_PAGE
    cursor.execute("SELECT COUNT(*) FROM messages")
    total_posts = cursor.fetchone()[0]
    total_pages = (total_posts + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE
    
    cursor.execute("SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?", (POSTS_PER_PAGE, offset))
    messages = cursor.fetchall()
    conn.close()
    
    logged_in = "username" in request.session
    username = request.session.get("username") if logged_in else None
    
    return templates.TemplateResponse(
        "bbs.html",
        {
            "request": request,
            "messages": messages,
            "current_page": page,
            "total_pages": total_pages,
            "logged_in": logged_in,
            "username": username
        }
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    request.session["username"] = username
    return RedirectResponse(url="/", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

@app.post("/post")
async def post_message(request: Request, message: str = Form(...)):
    if "username" not in request.session:
        raise HTTPException(status_code=403, detail="ログインが必要です。")
    
    name = request.session["username"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (name, message, timestamp) VALUES (?, ?, ?)",
        (name, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/", status_code=303)

# 削除用のパスを修正し、フォームからの投稿番号を受け取るようにします。
@app.post("/delete")
async def delete_message(request: Request, message_id: int = Form(...)):
    if "username" not in request.session:
        raise HTTPException(status_code=403, detail="ログインが必要です。")

    username = request.session["username"]
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM messages WHERE id = ?", (message_id,))
    message_owner = cursor.fetchone()
    if not message_owner or message_owner["name"] != username:
        conn.close()
        raise HTTPException(status_code=403, detail="この投稿を削除する権限がありません。")

    cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/", status_code=303)
