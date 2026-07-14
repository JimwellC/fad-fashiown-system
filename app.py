# app.py
# Fad Fashiown SaaS - Main Application Entry Point

import os
from flask import Flask, redirect, url_for
from flask_socketio import SocketIO, join_room
from flask_cors import CORS
from flask_login import current_user
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize extensions
from database import db, bcrypt, login_manager
from api.routes import set_socketio

# Initialize SocketIO
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')


def create_app():
    """Application factory"""
    app = Flask(__name__)

    # ── CONFIGURATION ──
    app.config['SECRET_KEY'] = os.getenv(
        'SECRET_KEY', 'fadfashiown_secret_2024'
    )

    base_dir = os.path.abspath(os.path.dirname(__file__))
    default_db = f"sqlite:///{os.path.join(base_dir, 'database', 'fadfashiown.db')}"
    database_url = os.getenv('DATABASE_URL', default_db)

    # Railway PostgreSQL fix
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True
    }

    # ── INITIALIZE EXTENSIONS ──
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://www.tiktok.com",
            "https://*.tiktok.com",
            "http://localhost:5000",
            "https://web-production-1fba.up.railway.app"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

    # ── LOGIN MANAGER ──
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please login to access the dashboard'
    login_manager.login_message_category = 'error'

    from auth.models import Client

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(Client, int(user_id))

    # ── REGISTER BLUEPRINTS ──
    from auth.routes import auth
    from dashboard.routes import dashboard
    from api.routes import api
    from api.facebook_routes import facebook

    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(api)
    app.register_blueprint(facebook)

    # ── CREATE DATABASE TABLES ──
    with app.app_context():
        if 'sqlite' in database_url:
            db_dir = os.path.join(base_dir, 'database')
            os.makedirs(db_dir, exist_ok=True)
        db.create_all()  # creates missing TABLES only (not new columns)
        # Additive column migrations for existing tables (Facebook feature).
        # create_all() cannot add columns to tables that already exist.
        from migrations import migrate_fb_columns
        migrate_fb_columns(db)
        print("✅ Database tables created")

    # ── PASS SOCKETIO TO API ──
    set_socketio(socketio)
    from api.facebook_routes import (
        set_socketio as set_fb_socketio, recover_pending_batches
    )
    set_fb_socketio(socketio)
    # Re-queue any Facebook auto-messages orphaned by a restart (opt-in via
    # FB_RECOVER_ON_BOOT=1 so imports/tests never trigger real sends).
    recover_pending_batches(app)

    return app


# ── SOCKETIO EVENTS ──
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        room = f"client_{current_user.id}"
        join_room(room)
        print(f"📱 Connected: {current_user.business_name}")


@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        print(f"📱 Disconnected: {current_user.business_name}")


# ── MAIN ENTRY POINT ──
app = create_app()

if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════╗
║     FAD FASHIOWN LIVE SELLING SYSTEM     ║
║            SaaS Version 1.0              ║
╚══════════════════════════════════════════╝
    """)
    print(f"🌐 App: http://localhost:5000")
    print(f"🔐 Login: http://localhost:5000/login")
    print("─" * 45)

    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('DEBUG', 'False') == 'True',
        use_reloader=False,
        # Local dev only (this __main__ block never runs under gunicorn, which is
        # how production starts). Lets the Werkzeug dev server start for local
        # testing without the "not designed for production" guard aborting it.
        allow_unsafe_werkzeug=True
    )
