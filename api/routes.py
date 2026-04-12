# api/routes.py
from flask import Blueprint, request, jsonify, make_response
from flask_login import login_required, current_user
from datetime import datetime
from database import db
from auth.models import Order
import json

api = Blueprint('api', __name__)

socketio_ref = None
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


# ── PUBLIC ENDPOINT - No login required ──
@api.route('/api/new-comment', methods=['POST', 'OPTIONS'])
def new_comment():
    """Receive comments from Chrome extension - public, uses token auth"""

    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            raw = request.get_data(as_text=True)
            data = json.loads(raw)
    except Exception:
        response = make_response(jsonify({"error": "Invalid data"}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    username = data.get('username', '').strip()
    message = data.get('message', '').strip()
    is_buyer = data.get('is_buyer', False)
    token = data.get('token', '').strip()

    if not username:
        response = make_response(jsonify({"error": "No username"}), 400)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    # Find client by token
    from auth.models import Client
    client = Client.query.filter_by(token=token).first()

    if not client:
        print(f"❌ Invalid token: {token[:10]}...")
        # Return ok anyway to avoid extension errors
        response = make_response(jsonify({"error": "Invalid token"}), 401)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    client_id = client.id
    print(f"💬 @{username}: '{message}' → {client.business_name}")

    if socketio_ref:
        socketio_ref.emit('new_comment', {
            "username": username,
            "message": message,
            "is_buyer": is_buyer
        }, room=f"client_{client_id}")

    response = make_response(jsonify({"success": True}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


# ── PROTECTED ENDPOINTS - Login required ──
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

    print(f"Buyer set: {username} (Client: {current_user.business_name})")

    if socketio_ref:
        socketio_ref.emit('buyer_detected', {
            "username": username,
            "detected_at": current_buyers[client_id]["detected_at"]
        }, room=f"client_{client_id}")

    return jsonify({"success": True, "username": username})


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

    order = Order(
        client_id=current_user.id,
        buyer_username=username,
        item_name=item_name,
        price=price,
        label_printed=True
    )
    db.session.add(order)
    db.session.commit()

    print(f"Order saved: {username} | {item_name} | ₱{price}")

    order_dict = order.to_dict()

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


@api.route('/api/qz-sign', methods=['POST'])
def qz_sign():
    """Sign QZ Tray requests with private key"""
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    import os

    try:
        data = request.get_json()
        to_sign = data.get('request', '')

        # Read private key
        key_path = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            '..', 'certs', 'private-key.pem'
        )

        with open(key_path, 'rb') as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)

        # Sign the request
        signature = private_key.sign(
            to_sign.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA512()
        )

        encoded = base64.b64encode(signature).decode('utf-8')
        return jsonify({'signature': encoded})

    except Exception as e:
        print(f'QZ Sign error: {e}')
        return jsonify({'signature': ''})


@api.route('/api/orders/<int:order_id>', methods=['DELETE'])
@login_required
def delete_order(order_id):
    """Delete a specific order - client can only delete their own"""
    order = Order.query.filter_by(
        id=order_id,
        client_id=current_user.id
    ).first()

    if not order:
        return jsonify({"error": "Order not found"}), 404

    db.session.delete(order)
    db.session.commit()

    print(f"🗑️ Order #{order_id} deleted by {current_user.business_name}")
    return jsonify({"success": True})


@api.route('/api/order-stats', methods=['GET'])
@login_required
def order_stats():
    """Get current order stats for this client"""
    orders = Order.query.filter_by(client_id=current_user.id).all()
    total_orders = len(orders)
    total_sales = sum(o.price for o in orders)
    avg_order = total_sales / total_orders if total_orders > 0 else 0

    return jsonify({
        'total_orders': total_orders,
        'total_sales': total_sales,
        'avg_order': avg_order
    })

@api.route('/api/pinned-comment', methods=['POST'])
def pinned_comment():
    """Receive pinned comment from Node.js TikTok listener"""
    try:
        data = request.get_json(force=True, silent=True)
        username = data.get('username', '').strip()
        message = data.get('message', '').strip()
        token = data.get('token', '').strip()

        if not username or not token:
            return jsonify({"error": "Missing data"}), 400

        from auth.models import Client
        client = Client.query.filter_by(token=token).first()
        if not client:
            return jsonify({"error": "Invalid token"}), 401

        client_id = client.id
        print(f"📌 Pinned comment: @{username}: '{message}' → {client.business_name}")

        # Auto-set as buyer and notify dashboard
        set_current_buyer(client_id, username)

        if socketio_ref:
            # Notify dashboard of pinned buyer
            socketio_ref.emit('buyer_detected', {
                "username": username,
                "detected_at": current_buyers[client_id]["detected_at"],
                "pinned": True,
                "message": message
            }, room=f"client_{client_id}")

            # Also show in comments panel
            socketio_ref.emit('new_comment', {
                "username": username,
                "message": f"📌 {message}",
                "is_buyer": True,
                "pinned": True
            }, room=f"client_{client_id}")

        response = make_response(jsonify({"success": True}))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    except Exception as e:
        print(f"Pinned comment error: {e}")
        return jsonify({"error": str(e)}), 500


@api.route('/api/start-pin-detection', methods=['POST'])
@login_required
def start_pin_detection():
    """Tell Node.js service to start listening to client's TikTok live"""
    import requests as req
    import os

    tiktok_username = current_user.tiktok_username
    if not tiktok_username:
        return jsonify({"error": "No TikTok username set in Settings"}), 400

    tiktok_username = tiktok_username.replace('@', '').strip()

    railway_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
    if railway_domain:
        flask_url = f'https://{railway_domain}'
    else:
        flask_url = 'http://localhost:5000'

    node_url = os.environ.get('NODE_LISTENER_URL', 'http://localhost:3000')

    try:
        response = req.post(f'{node_url}/start', json={
            'tiktok_username': tiktok_username,
            'client_token': current_user.token,
            'flask_url': flask_url
        }, timeout=10)

        data = response.json()
        if data.get('success'):
            return jsonify({
                "success": True,
                "message": f"Listening to @{tiktok_username}"
            })
        else:
            return jsonify({"error": data.get('error', 'Failed to connect')}), 500

    except Exception as e:
        return jsonify({
            "error": f"Could not connect: {str(e)}"
        }), 500