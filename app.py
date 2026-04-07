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
    """Application factory - creates and configures Flask app"""
    app = Flask(__name__)

    # ── CONFIGURATION ──
    app.config['SECRET_KEY'] = os.getenv(
        'SECRET_KEY', 'fadfashiown_secret_2024'
    )
    base_dir = os.path.abspath(os.path.dirname(__file__))
    default_db = f"sqlite:///{os.path.join(base_dir, 'database', 'fadfashiown.db')}"
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', default_db)

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True
    }

    # Rate limiting - prevent brute force attacks
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )

    # ── INITIALIZE EXTENSIONS ──
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app)
    CORS(app)

    # ── LOGIN MANAGER SETTINGS ──
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please login to access the dashboard'
    login_manager.login_message_category = 'error'

    # User loader for Flask-Login
    from auth.models import Client

    @login_manager.user_loader
    def load_user(user_id):
        return Client.query.get(int(user_id))

    # ── REGISTER BLUEPRINTS ──
    from auth.routes import auth
    from dashboard.routes import dashboard
    from api.routes import api

    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(api)

    # ── CREATE DATABASE TABLES ──
    with app.app_context():
        # Get absolute path to database folder
        base_dir = os.path.abspath(os.path.dirname(__file__))
        db_dir = os.path.join(base_dir, 'database')
        os.makedirs(db_dir, exist_ok=True)
        db.create_all()
        print("✅ Database tables created")

    # ── PASS SOCKETIO TO API ──
    set_socketio(socketio)

    return app


# ── SOCKETIO EVENTS ──
@socketio.on('connect')
def handle_connect():
    """Client dashboard connected"""
    if current_user.is_authenticated:
        # Join a room specific to this client
        room = f"client_{current_user.id}"
        join_room(room)
        print(f"📱 Dashboard connected: {current_user.business_name}")


@socketio.on('disconnect')
def handle_disconnect():
    """Client dashboard disconnected"""
    if current_user.is_authenticated:
        print(f"📱 Dashboard disconnected: {current_user.business_name}")


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
        port=5000,
        debug=True,
        use_reloader=False
    )