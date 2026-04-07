# api/routes.py
# API endpoints - all protected by login

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from flask_socketio import emit
from datetime import datetime
from database import db
from auth.models import Order
import json

api = Blueprint('api', __name__)

# Store socketio reference (set in app.py)
socketio_ref = None

# Current buyer per client session
current_buyers = {}


def set_socketio(sio):
    global socketio_ref
    socketio_ref = sio


def get_current_buyer(client_id):
    return current_buyers.get(client_id, {
        "username": "",
        "detected_at": None
    })


def set_current_buyer(client_id, username):
    current_buyers[client_id] = {
        "username": username,
        "detected_at": datetime.now().strftime("%H:%M:%S")
    }


@api.route('/api/set-buyer', methods=['POST'])
@login_required
def set_buyer():
    """Set the current buyer for this client's session"""
    data = request.get_json()
    username = data.get('username', '').strip()

    if not username:
        return jsonify({"error": "Username required"}), 400

    client_id = current_user.id
    set_current_buyer(client_id, username)

    print(f"✅ Buyer set: {username} (Client: {current_user.business_name})")

    # Notify this client's dashboard
    if socketio_ref:
        socketio_ref.emit('buyer_detected', {
            "username": username,
            "detected_at": current_buyers[client_id]["detected_at"]
        }, room=f"client_{client_id}")

    return jsonify({"success": True, "username": username})


@api.route('/api/new-comment', methods=['POST', 'OPTIONS'])
@login_required
def new_comment():
    """Receive comments from Chrome extension"""
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = '*'
        return response

    try:
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            data = json.loads(request.get_data(as_text=True))
    except Exception as e:
        return jsonify({"error": "Invalid data"}), 400

    if not data:
        return jsonify({"error": "No data"}), 400

    username = data.get('username', '').strip()
    message = data.get('message', '').strip()
    is_buyer = data.get('is_buyer', False)

    if not username:
        return jsonify({"error": "No username"}), 400

    client_id = current_user.id

    print(f"💬 Comment: @{username}: '{message}' "
          f"(Client: {current_user.business_name})")

    # Push to this client's dashboard only
    if socketio_ref:
        socketio_ref.emit('new_comment', {
            "username": username,
            "message": message,
            "is_buyer": is_buyer
        }, room=f"client_{client_id}")

    if is_buyer:
        set_current_buyer(client_id, username)

    return jsonify({"success": True})


@api.route('/api/print-label', methods=['POST'])
@login_required
def print_label():
    """Save order and trigger label print"""
    data = request.get_json()

    username = data.get('username', '').strip()
    item_name = data.get('item_name', '').strip()
    price = data.get('price', 0)

    if not username:
        return jsonify({"error": "Username required"}), 400
    if not item_name:
        return jsonify({"error": "Item name required"}), 400
    if not price:
        return jsonify({"error": "Price required"}), 400

    try:
        price = float(price)
    except ValueError:
        return jsonify({"error": "Invalid price"}), 400

    # Save order linked to this client
    order = Order(
        client_id=current_user.id,
        buyer_username=username,
        item_name=item_name,
        price=price,
        label_printed=True
    )
    db.session.add(order)
    db.session.commit()

    print(f"🖨️  Order saved: {username} | {item_name} | "
          f"₱{price} (Client: {current_user.business_name})")

    order_dict = order.to_dict()

    # Notify this client's dashboard
    if socketio_ref:
        socketio_ref.emit('order_saved', order_dict,
                         room=f"client_{current_user.id}")

    return jsonify({"success": True, "order": order_dict})


@api.route('/api/orders', methods=['GET'])
@login_required
def get_orders():
    """Get orders for this client only"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    orders = Order.query.filter_by(
        client_id=current_user.id
    ).order_by(
        Order.timestamp.desc()
    ).limit(per_page).offset((page - 1) * per_page).all()

    return jsonify([o.to_dict() for o in orders])


@api.route('/api/current-buyer', methods=['GET'])
@login_required
def get_current_buyer_route():
    """Get current buyer for this client"""
    buyer = get_current_buyer(current_user.id)
    return jsonify(buyer)