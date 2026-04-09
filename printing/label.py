# printing/label.py
# Label data structure for Fad Fashiown orders

from datetime import datetime


class Label:
    """Represents a printable order label"""

    def __init__(self, buyer_username, item_name, price, order_id=None):
        self.buyer_username = buyer_username
        self.item_name = item_name
        self.price = price
        self.order_id = order_id
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            'buyer_username': self.buyer_username,
            'item_name': self.item_name,
            'price': self.price,
            'order_id': self.order_id,
            'timestamp': self.timestamp.strftime('%b %d, %Y %I:%M %p')
        }

    def format_price(self):
        return f'₱{self.price:.2f}'

    def format_date(self):
        return self.timestamp.strftime('%b %d, %Y')

    def format_time(self):
        return self.timestamp.strftime('%I:%M %p')