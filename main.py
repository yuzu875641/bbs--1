# main.py
import sqlite3
from fastapi import FastAPI, Form, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from datetime import datetime

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="a_very_secret_key_here")

# テンプレートエンジンを設定
templates = Jinja2Templates(directory="templates")

# データベースの初期化と接続
DATABASE = "bbs.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # 列名でアクセスできるようにする
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    # 初回起動時にダミーユーザーを作成
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', 'password123'))
        conn.commit()
    except sqlite3.IntegrityError:
        # ユーザーが既に存在する場合は何もしない
        pass
    conn.close()

# サーバー起動時にデータベースを初期化
init_db()

# 1ページあたりの投稿数
POSTS_PER_PAGE = 10

# トップページ (掲示板の表示とページネーション)
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, page: int = Query(1, ge=1)):
    conn = get_db_connection()
    cursor = conn.cursor()

    # ページネーションのための計算
    offset = (page - 1) * POSTS_PER_PAGE
    cursor.execute("SELECT COUNT(*) FROM messages")
    total_posts = cursor.fetchone()[0]
    total_pages = (total_posts + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE

    # メッセージの取得
    cursor.execute("SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?", (POSTS_PER_PAGE, offset))
    messages = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse(
        "bbs.html",
        {
            "request": request,
            "messages": messages,
            "current_page": page,
            "total_pages": total_pages,
            "logged_in": "user" in request.session
        }
    )

# ログインページ
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# ログイン処理
@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=303)
    
    return HTMLResponse(content="ログインに失敗しました。<a href='/login'>再試行</a>")

# ログアウト処理
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

# 投稿の作成
@app.post("/post")
async def post_message(request: Request, message: str = Form(...)):
    if "user" not in request.session:
        raise HTTPException(status_code=403, detail="ログインが必要です。")
    
    name = request.session["user"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (name, message, timestamp) VALUES (?, ?, ?)",
        (name, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/", status_code=303)

# 投稿の削除
@app.post("/delete/{message_id}")
async def delete_message(request: Request, message_id: int):
    if "user" not in request.session:
        raise HTTPException(status_code=403, detail="ログインが必要です。")

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 投稿がログインユーザーのものであるかを確認
    cursor.execute("SELECT name FROM messages WHERE id = ?", (message_id,))
    message_owner = cursor.fetchone()
    if not message_owner or message_owner["name"] != request.session["user"]:
        conn.close()
        raise HTTPException(status_code=403, detail="この投稿を削除する権限がありません。")

    cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/", status_code=303)

# 投稿の編集
@app.post("/edit/{message_id}")
async def edit_message(request: Request, message_id: int, new_message: str = Form(...)):
    if "user" not in request.session:
        raise HTTPException(status_code=403, detail="ログインが必要です。")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 投稿がログインユーザーのものであるかを確認
    cursor.execute("SELECT name FROM messages WHERE id = ?", (message_id,))
    message_owner = cursor.fetchone()
    if not message_owner or message_owner["name"] != request.session["user"]:
        conn.close()
        raise HTTPException(status_code=403, detail="この投稿を編集する権限がありません。")

    cursor.execute(
        "UPDATE messages SET message = ? WHERE id = ?",
        (new_message, message_id)
    )
    conn.commit()
    conn.close()
    
    return RedirectResponse(url="/", status_code=303)
