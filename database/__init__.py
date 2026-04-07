# database/__init__.py
# Database extensions - initialized here, used across the app

from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

# Initialize extensions (not yet bound to app)
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()