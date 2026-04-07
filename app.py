# app.py
# The brain of the Fad Fashiown System
# This is the main Flask backend that runs everything

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import sqlite3
import os
import threading
import time
from datetime import datetime
import config

# --- APP INITIALIZATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'fadfashiown2024secretkey'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- GLOBAL STATE ---
# Stores the current detected buyer username
current_buyer = {
    "username": "",
    "detected_at": None
}

# Stores the last confirmed username to prevent duplicates
last_confirmed_username = ""

# Controls whether the detection loop is running
detection_active = False
detection_thread = None


# ─────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────

def init_database():
    """Create the database and orders table if they don't exist"""
    # Make sure the database folder exists
    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    # Create orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            item_name TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL,
            label_printed INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Database initialized")


def save_order(username, item_name, price):
    """Save a new order to the database"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        INSERT INTO orders (username, item_name, price, timestamp, label_printed)
        VALUES (?, ?, ?, ?, 1)
    ''', (username, item_name, price, timestamp))

    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": order_id,
        "username": username,
        "item_name": item_name,
        "price": price,
        "timestamp": timestamp
    }


def get_recent_orders(limit=20):
    """Get the most recent orders from the database"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, username, item_name, price, timestamp
        FROM orders
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))

    rows = cursor.fetchall()
    conn.close()

    # Convert to list of dictionaries
    orders = []
    for row in rows:
        orders.append({
            "id": row[0],
            "username": row[1],
            "item_name": row[2],
            "price": row[3],
            "timestamp": row[4]
        })

    return orders


# ─────────────────────────────────────────
# DETECTION ENGINE (Placeholder for Phase 2)
# ─────────────────────────────────────────

def detection_loop():
    """
    Background thread that continuously scans the screen
    for pinned comments using OCR.
    """
    global detection_active

    # Import detection modules
    from detection.capture import capture_region
    from detection.ocr import detect_pinned_username
    from detection.calibration import load_calibration

    print("🔍 Detection loop started")

    # Load calibration zone if available
    calibration = load_calibration()
    if calibration:
        zone = calibration
        print(f"📐 Using calibrated zone: {zone}")
    else:
        zone = config.CAPTURE_ZONE
        print("⚠️  No calibration found, using default zone from config.py")
        print("   Run calibration tool for better accuracy!")

    while detection_active:
        try:
            # Step 1: Capture the screen region
            img = capture_region(zone)

            # Step 2: Run OCR and get confirmed username
            username = detect_pinned_username(img)

            # Step 3: If valid username detected, update dashboard
            if username:
                update_buyer(username)

            # Wait before next scan
            time.sleep(config.SCAN_INTERVAL)

        except Exception as e:
            print(f"❌ Detection error: {e}")
            time.sleep(2)

    print("🛑 Detection loop stopped")

def update_buyer(username):
    """
    Called when a new pinned username is detected.
    Updates global state and notifies the dashboard.
    """
    global current_buyer, last_confirmed_username

    # Clean up the username
    username = username.strip()

    # Ignore if same as last confirmed (duplicate prevention)
    if username == last_confirmed_username:
        return

    if len(username) < config.MIN_USERNAME_LENGTH:
        return

    # Update state
    current_buyer["username"] = username
    current_buyer["detected_at"] = datetime.now().strftime("%H:%M:%S")
    last_confirmed_username = username

    print(f"✅ New buyer detected: {username}")

    # Push to dashboard via WebSocket instantly
    socketio.emit('buyer_detected', {
        "username": username,
        "detected_at": current_buyer["detected_at"]
    })


# ─────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────

@app.route('/')
def dashboard():
    """Serve the main dashboard page"""
    return render_template('dashboard.html',
                           app_name=config.APP_NAME,
                           business_name=config.BUSINESS_NAME)


@app.route('/api/current-buyer', methods=['GET'])
def get_current_buyer():
    """Return the currently detected buyer"""
    return jsonify(current_buyer)


@app.route('/api/set-buyer', methods=['POST'])
def set_buyer_manually():
    """
    Allow manual input of buyer username
    Used as fallback when OCR fails
    """
    data = request.get_json()
    username = data.get('username', '').strip()

    if not username:
        return jsonify({"error": "Username is required"}), 400

    update_buyer(username)
    return jsonify({"success": True, "username": username})

@app.route('/api/new-comment', methods=['POST', 'OPTIONS'])
def new_comment():
    """
    Receives comments from Chrome extension.
    Accepts text/plain to bypass CORS preflight.
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = '*'
        return response

    # Accept both JSON and text/plain (from extension)
    try:
        if request.content_type and 'application/json' in request.content_type:
            data = request.get_json()
        else:
            # Extension sends as text/plain to avoid CORS preflight
            import json
            data = json.loads(request.get_data(as_text=True))
    except Exception as e:
        print(f"❌ Parse error: {e}")
        return jsonify({"error": "Invalid data"}), 400

    if not data:
        return jsonify({"error": "No data"}), 400

    username = data.get('username', '').strip()
    message = data.get('message', '').strip()
    is_buyer = data.get('is_buyer', False)

    if not username:
        return jsonify({"error": "No username"}), 400

    print(f"💬 Comment received: @{username}: '{message}' {'🛒' if is_buyer else ''}")

    # Push to dashboard via WebSocket
    socketio.emit('new_comment', {
        "username": username,
        "message": message,
        "is_buyer": is_buyer
    })

    # If buyer comment, auto-set as current buyer
    if is_buyer:
        update_buyer(username)

    return jsonify({"success": True})

@app.route('/api/print-label', methods=['POST'])
def print_label():
    """
    Receive order details and trigger label printing
    """
    data = request.get_json()

    username = data.get('username', '').strip()
    item_name = data.get('item_name', '').strip()
    price = data.get('price', 0)

    # Validate inputs
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not item_name:
        return jsonify({"error": "Item name is required"}), 400
    if not price:
        return jsonify({"error": "Price is required"}), 400

    try:
        price = float(price)
    except ValueError:
        return jsonify({"error": "Price must be a number"}), 400

    # Save order to database
    order = save_order(username, item_name, price)

    # Phase 4 will add actual printing here
    # For now we just confirm the save
    print(f"🖨️  Label request: {username} | {item_name} | ₱{price}")

    # Notify dashboard that order was saved
    socketio.emit('order_saved', order)

    return jsonify({
        "success": True,
        "order": order,
        "message": "Order saved! (Printing will be added in Phase 4)"
    })


@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Return list of recent orders"""
    orders = get_recent_orders()
    return jsonify(orders)


@app.route('/api/detection/start', methods=['POST'])
def start_detection():
    """Start the background detection loop"""
    global detection_active, detection_thread

    if detection_active:
        return jsonify({"message": "Detection already running"})

    detection_active = True
    detection_thread = threading.Thread(target=detection_loop, daemon=True)
    detection_thread.start()

    return jsonify({"success": True, "message": "Detection started"})


@app.route('/api/detection/stop', methods=['POST'])
def stop_detection():
    """Stop the background detection loop"""
    global detection_active

    detection_active = False
    return jsonify({"success": True, "message": "Detection stopped"})


@app.route('/api/detection/status', methods=['GET'])
def detection_status():
    """Return whether detection is currently active"""
    return jsonify({"active": detection_active})

@app.route('/api/calibrate', methods=['POST'])
def run_calibration_tool():
    """Launch the calibration tool in a separate thread"""
    import threading
    from detection.calibration import run_calibration

    def calibrate():
        run_calibration()

    thread = threading.Thread(target=calibrate, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "message": "Calibration tool launched. Draw a box around the pinned comment area."
    })


# ─────────────────────────────────────────
# WEBSOCKET EVENTS
# ─────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    """Called when dashboard connects"""
    print("📱 Dashboard connected")
    # Send current buyer immediately on connect
    emit('buyer_detected', current_buyer)


@socketio.on('disconnect')
def handle_disconnect():
    """Called when dashboard disconnects"""
    print("📱 Dashboard disconnected")


# ─────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────

if __name__ == '__main__':
    print(f"""
╔══════════════════════════════════════════╗
║     FAD FASHIOWN LIVE SELLING SYSTEM     ║
║          Starting up...                  ║
╚══════════════════════════════════════════╝
    """)

    # Initialize database on startup
    init_database()

    print(f"🌐 Dashboard: http://localhost:{config.PORT}")
    print(f"📦 Database: {config.DATABASE_PATH}")
    print(f"🔍 Detection: Ready (start from dashboard)")
    print("─" * 45)

    # Start the Flask app with WebSocket support
    socketio.run(
        app,
        host='0.0.0.0',
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=False  # Prevents double-starting threads
    )