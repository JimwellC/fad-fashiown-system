# auth/models.py
from datetime import datetime
from flask_login import UserMixin
from database import db, bcrypt


class Client(UserMixin, db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    business_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    plan = db.Column(db.String(20), default='active')
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    tiktok_username = db.Column(db.String(100), default='')
    must_change_password = db.Column(db.Boolean, default=False)

    orders = db.relationship('Order', backref='client', lazy=True)
    token = db.Column(db.String(64), unique=True, nullable=True)

    # Detection settings
    detection_mode = db.Column(db.String(20), default='keywords')
    custom_keywords = db.Column(db.Text, default='mine')
    highlight_numbers = db.Column(db.Boolean, default=False)

    # Label settings
    label_title = db.Column(db.String(100), default='FAD FASHIOWN')
    label_tagline = db.Column(db.String(100), default='Live Selling')
    label_template = db.Column(db.String(20), default='classic')
    label_show_order_id = db.Column(db.Boolean, default=True)
    label_show_datetime = db.Column(db.Boolean, default=True)

    # ── Facebook Auto-Messenger settings ──
    # NOTE: columns added to the live DB via migrations.migrate_fb_columns()
    # (ALTER TABLE), NOT db.create_all(). See migrations.py.
    facebook_page_token = db.Column(db.Text)              # long-lived Page Access Token (secret; can exceed 255 chars)
    facebook_page_id = db.Column(db.String(64))           # FB Page ID (auto-resolved from the token)
    facebook_page_name = db.Column(db.String(120))        # Page name, for "Connected as: ..." display
    fb_auto_message_enabled = db.Column(db.Boolean, default=False)
    fb_message_template = db.Column(db.Text)              # editable Tagalog template (blank = default)
    fb_message_delay = db.Column(db.Integer, default=4)  # batch window in minutes (3/4/5)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(
            password
        ).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Client {self.business_name}>'


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.Integer,
        db.ForeignKey('clients.id'),
        nullable=False
    )
    buyer_username = db.Column(db.String(100), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    label_printed = db.Column(db.Boolean, default=False)

    # ── Facebook Auto-Messenger fields ──
    # Added to the live DB via migrations.migrate_fb_columns() (ALTER TABLE).
    platform = db.Column(db.String(20), default='tiktok')  # 'tiktok' | 'facebook'
    buyer_psid = db.Column(db.String(64))                  # FB Page-Scoped User ID (Send API fallback)
    fb_comment_id = db.Column(db.String(64))               # FB live comment id (for Private Replies)
    message_sent = db.Column(db.Boolean, default=False)
    message_failed = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'username': self.buyer_username,
            'item_name': self.item_name,
            'price': self.price,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'label_printed': self.label_printed,
            'platform': self.platform or 'tiktok',
            'message_sent': bool(self.message_sent),
            'message_failed': bool(self.message_failed)
        }
