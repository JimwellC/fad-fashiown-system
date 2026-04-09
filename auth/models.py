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

    orders = db.relationship('Order', backref='client', lazy=True)
    token = db.Column(db.String(64), unique=True, nullable=True)

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

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'username': self.buyer_username,
            'item_name': self.item_name,
            'price': self.price,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'label_printed': self.label_printed
        }
