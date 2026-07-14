# api/facebook_routes.py
"""
Facebook Auto-Messenger — Section 9.

Pipeline (kept SEPARATE from the TikTok pipeline):

    Graph API live comments  ->  dashboard "Live Comments" panel (SocketIO)
    seller clicks winner + enters price  ->  Order(platform='facebook', fb_comment_id)
    order saved  ->  batched (threading.Timer) consolidated Private Reply

HARD GUARD: the consumer only runs for a client when
    fb_auto_message_enabled == True  AND  a non-empty facebook_page_token
(and a facebook_page_id to locate the live video). If any is missing the
consumer never starts and the TikTok pipeline is completely unaffected.

NOTE: This is built against the EXPECTED Graph API response shapes. The exact
field names / API version are validated against a real dev Page + test live
stream before go-live (see GRAPH_API_VERSION and the fetch helpers).
"""
import re
import threading
from datetime import datetime

import requests as req
from flask import Blueprint, jsonify, current_app
from flask_login import login_required, current_user

from database import db
from auth.models import Client, Order
from fb_defaults import DEFAULT_FB_TEMPLATE

facebook = Blueprint('facebook', __name__)

# ── Graph API config (validate/bump when testing against the dev Page) ──
GRAPH_API_VERSION = 'v21.0'
GRAPH_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'
POLL_INTERVAL_SECONDS = 3        # live-comments poll cadence (SSE is a later option)
SEND_RETRY_DELAY_SECONDS = 30    # per handoff: retry once after 30s, then fail
HTTP_TIMEOUT = 15

socketio_ref = None

# In-memory state — safe because we run a SINGLE Gunicorn worker.
#   _consumers[client_id] = {'stop': threading.Event}
#   _pending[client_id][buyer_key] = {
#       'timer': threading.Timer, 'order_ids': [...],
#       'comment_id': str|None, 'psid': str|None
#   }
_consumers = {}
_consumers_lock = threading.Lock()
_pending = {}
_pending_lock = threading.Lock()


def set_socketio(sio):
    global socketio_ref
    socketio_ref = sio


# ──────────────────────────────────────────────────────────────────────────
#  Buyer detection (mirrors chrome-extension/content.js so FB comments get the
#  same green highlight as TikTok comments)
# ──────────────────────────────────────────────────────────────────────────
def _is_number_code(msg):
    t = msg.strip()
    return bool(
        re.fullmatch(r'\d+', t) or
        re.fullmatch(r'[lL]\d+', t) or
        re.fullmatch(r'\d+[lL]', t) or
        re.fullmatch(r'(?i)lock\s*\d+', t) or
        re.fullmatch(r'(?i)l\s*\d+', t)
    )


def _is_buyer(message, mode, keywords):
    msg = (message or '').lower().strip()
    def has_kw():
        return any(
            msg == k or msg.startswith(k + ' ') or
            msg.endswith(' ' + k) or (' ' + k + ' ') in msg
            for k in keywords if k
        )
    if mode == 'numbers':
        return _is_number_code(message or '')
    if mode == 'both':
        return has_kw() or _is_number_code(message or '')
    return has_kw()  # 'keywords' (default)


# ──────────────────────────────────────────────────────────────────────────
#  Graph API helpers (expected shapes — validated live later)
# ──────────────────────────────────────────────────────────────────────────
def resolve_page_from_token(token):
    """Ask Graph who this Page Access Token belongs to.

    Returns (page_id, page_name, error). This is what lets the client paste ONLY
    the token — we derive the Page ID ourselves and can confirm the token works
    before they ever go live.
    """
    try:
        r = req.get(
            f'{GRAPH_BASE}/me',
            params={'fields': 'id,name', 'access_token': token},
            timeout=HTTP_TIMEOUT,
        )
        data = r.json()
        if 'error' in data:
            return None, None, data['error'].get('message', 'Invalid token')
        if not data.get('id'):
            return None, None, 'Token did not resolve to a Page'
        return data.get('id'), data.get('name'), None
    except Exception as e:
        return None, None, str(e)


def _resolve_live_video_id(page_id, token):
    """Return the id of the Page's currently-LIVE video, or None."""
    try:
        r = req.get(
            f'{GRAPH_BASE}/{page_id}/live_videos',
            params={'fields': 'id,status', 'limit': 5, 'access_token': token},
            timeout=HTTP_TIMEOUT,
        )
        data = r.json()
        for v in data.get('data', []):
            if str(v.get('status', '')).upper() == 'LIVE':
                return v.get('id')
    except Exception as e:
        print(f'FB resolve_live_video error: {e}')
    return None


def _fetch_comments(live_video_id, token):
    """Return the list of comment dicts for a live video (expected shape:
    {id, from:{id,name}, message, created_time})."""
    try:
        r = req.get(
            f'{GRAPH_BASE}/{live_video_id}/comments',
            params={'fields': 'id,from,message,created_time', 'access_token': token},
            timeout=HTTP_TIMEOUT,
        )
        return r.json().get('data', [])
    except Exception as e:
        print(f'FB fetch_comments error: {e}')
        return []


# ──────────────────────────────────────────────────────────────────────────
#  Live-comment consumer (background task, guarded)
# ──────────────────────────────────────────────────────────────────────────
def _consume_loop(app, client_id):
    seen = set()
    live_video_id = None

    with _consumers_lock:
        info = _consumers.get(client_id)
    if not info:
        return
    stop = info['stop']

    while not stop.is_set():
        # Re-read settings each pass so a Settings change / disable takes effect,
        # and so the guard is continuously enforced.
        with app.app_context():
            client = db.session.get(Client, client_id)
            if not (client and client.fb_auto_message_enabled
                    and client.facebook_page_token and client.facebook_page_id):
                break
            token = client.facebook_page_token
            page_id = client.facebook_page_id
            mode = client.detection_mode or 'keywords'
            keywords = [k.strip().lower() for k in
                        (client.custom_keywords or 'mine').split(',') if k.strip()]

        if not live_video_id:
            # Auto-discover the Page's current LIVE broadcast. If none is running
            # yet we simply keep polling, so Start can be pressed before going live.
            live_video_id = _resolve_live_video_id(page_id, token)
            if not live_video_id:
                stop.wait(POLL_INTERVAL_SECONDS)
                continue
            print(f'FB: watching live video {live_video_id} (auto-discovered)')

        for c in _fetch_comments(live_video_id, token):
            cid = c.get('id')
            if not cid or cid in seen:
                continue
            seen.add(cid)
            frm = c.get('from') or {}
            username = frm.get('name') or 'Facebook User'
            message = c.get('message', '') or ''
            if socketio_ref:
                socketio_ref.emit('new_comment', {
                    'username': username,
                    'message': message,
                    'is_buyer': _is_buyer(message, mode, keywords),
                    'platform': 'facebook',
                    'comment_id': cid,
                    'from_id': frm.get('id'),
                }, room=f'client_{client_id}')

        stop.wait(POLL_INTERVAL_SECONDS)

    with _consumers_lock:
        _consumers.pop(client_id, None)


def start_fb_consumer(app, client):
    """Start the consumer for a client if the guard passes and it's not already
    running. Returns (started: bool, reason: str)."""
    if not client.fb_auto_message_enabled:
        return False, ("Turn on 'Enable Facebook auto-messaging' in "
                       "Settings → Facebook")
    if not client.facebook_page_token:
        return False, 'Paste your Page Access Token in Settings → Facebook'
    if not client.facebook_page_id:
        return False, ('No Facebook Page detected — paste a valid Page Access '
                       'Token in Settings → Facebook')
    if socketio_ref is None:
        return False, 'Server not ready'

    with _consumers_lock:
        if client.id in _consumers:
            return True, 'already running'
        _consumers[client.id] = {'stop': threading.Event()}

    socketio_ref.start_background_task(_consume_loop, app, client.id)
    return True, 'started'


def stop_fb_consumer(app, client_id):
    with _consumers_lock:
        info = _consumers.get(client_id)
        if info:
            info['stop'].set()
    # Any batched messages still pending are flushed immediately (live ended).
    flush_pending_for_client(app, client_id)


# ──────────────────────────────────────────────────────────────────────────
#  Batching + sending (threading.Timer)
# ──────────────────────────────────────────────────────────────────────────
def schedule_message_for_order(app, client, order):
    """Add a saved FB order to its buyer's batch and (re)start the timer.

    Called from /api/print-label after an order is committed. Guarded: no-op
    unless auto-messaging is enabled and a token exists.
    """
    if not (client.fb_auto_message_enabled and client.facebook_page_token):
        return
    buyer_key = order.buyer_username
    delay = (client.fb_message_delay or 4) * 60

    with _pending_lock:
        by_buyer = _pending.setdefault(client.id, {})
        entry = by_buyer.get(buyer_key)
        if entry and entry.get('timer'):
            entry['timer'].cancel()          # reset window on each new win
        if not entry:
            entry = {'timer': None, 'order_ids': [], 'comment_id': None, 'psid': None}
            by_buyer[buyer_key] = entry

        entry['order_ids'].append(order.id)
        if order.fb_comment_id:
            entry['comment_id'] = order.fb_comment_id   # keep latest comment id
        if order.buyer_psid:
            entry['psid'] = order.buyer_psid

        timer = threading.Timer(delay, _fire_batch, args=(app, client.id, buyer_key))
        timer.daemon = True
        entry['timer'] = timer
        timer.start()


def _fire_batch(app, client_id, buyer_key):
    with _pending_lock:
        entry = _pending.get(client_id, {}).pop(buyer_key, None)
    if not entry:
        return

    with app.app_context():
        client = db.session.get(Client, client_id)
        orders = [o for o in (db.session.get(Order, oid) for oid in entry['order_ids']) if o]
        if not client or not orders:
            return

        ok, err = _send_consolidated(client, orders, entry.get('comment_id'), entry.get('psid'))
        for o in orders:
            o.message_sent = bool(ok)
            o.message_failed = not ok
        db.session.commit()

        if socketio_ref:
            socketio_ref.emit('fb_message_status', {
                'buyer': buyer_key,
                'sent': bool(ok),
                'error': err,
                'order_ids': entry['order_ids'],
            }, room=f'client_{client_id}')
        db.session.remove()


def flush_pending_for_client(app, client_id):
    """Force-send all pending batches for a client (Stop Detection / live end)."""
    with _pending_lock:
        keys = list(_pending.get(client_id, {}).keys())
        for k in keys:
            entry = _pending[client_id].get(k)
            if entry and entry.get('timer'):
                entry['timer'].cancel()
    for k in keys:
        _fire_batch(app, client_id, k)


def render_message(template, buyer_name, orders, when):
    """Render the Tagalog message from the template + batched orders."""
    template = template or DEFAULT_FB_TEMPLATE
    item_lines = '\n'.join(
        f'📦 {(o.item_name or "Item")} — ₱{o.price:.2f}' for o in orders
    )
    total = sum(o.price for o in orders)
    total_line = '' if len(orders) <= 1 else f'💰 Kabuuan: ₱{total:.2f}'
    timestamp = when.strftime('%b %d, %Y %I:%M %p')

    fields = dict(buyer_name=buyer_name, items=item_lines,
                  total=total_line, timestamp=timestamp)
    try:
        msg = template.format(**fields)
    except (KeyError, IndexError, ValueError):
        # Client typed an invalid placeholder — fall back to the default template.
        msg = DEFAULT_FB_TEMPLATE.format(**fields)

    while '\n\n\n' in msg:          # collapse the gap left by an empty {total}
        msg = msg.replace('\n\n\n', '\n\n')
    return msg.strip()


def _send_consolidated(client, orders, comment_id, psid):
    """Send one message; retry once after 30s on failure. Returns (ok, error)."""
    import time
    msg = render_message(
        client.fb_message_template, orders[0].buyer_username, orders,
        orders[-1].timestamp or datetime.utcnow(),
    )
    err = None
    for attempt in (1, 2):
        ok, err = _do_send(client, msg, comment_id, psid)
        if ok:
            return True, None
        if attempt == 1:
            time.sleep(SEND_RETRY_DELAY_SECONDS)
    return False, err


def _do_send(client, message, comment_id, psid):
    """Preferred: Private Replies by comment_id (no PSID needed).
    Fallback: Send API by PSID (only works if the buyer messaged the Page)."""
    token = client.facebook_page_token

    if comment_id:
        try:
            r = req.post(
                f'{GRAPH_BASE}/{comment_id}/private_replies',
                data={'message': message, 'access_token': token},
                timeout=HTTP_TIMEOUT,
            )
            body = r.json()
            if r.status_code == 200 and 'error' not in body:
                return True, None
            err = body.get('error', {}).get('message', r.text)
        except Exception as e:
            err = str(e)
    else:
        err = 'no comment_id available'

    if psid and client.facebook_page_id:
        try:
            r = req.post(
                f'{GRAPH_BASE}/{client.facebook_page_id}/messages',
                params={'access_token': token},
                json={'recipient': {'id': psid},
                      'messaging_type': 'RESPONSE',
                      'message': {'text': message}},
                timeout=HTTP_TIMEOUT,
            )
            body = r.json()
            if r.status_code == 200 and 'error' not in body:
                return True, None
            err = body.get('error', {}).get('message', r.text)
        except Exception as e:
            err = str(e)

    return False, err


# ──────────────────────────────────────────────────────────────────────────
#  Endpoints (login required) — control the FB consumer
# ──────────────────────────────────────────────────────────────────────────
@facebook.route('/api/facebook/start-detection', methods=['POST'])
@login_required
def start_detection():
    started, reason = start_fb_consumer(current_app._get_current_object(), current_user)
    if not started:
        return jsonify({'error': reason}), 400
    return jsonify({'success': True, 'message': 'Facebook detection started'})


@facebook.route('/api/facebook/stop-detection', methods=['POST'])
@login_required
def stop_detection():
    stop_fb_consumer(current_app._get_current_object(), current_user.id)
    return jsonify({'success': True, 'message': 'Facebook detection stopped'})


@facebook.route('/api/facebook/status', methods=['GET'])
@login_required
def status():
    with _consumers_lock:
        running = current_user.id in _consumers
    return jsonify({'running': running})
