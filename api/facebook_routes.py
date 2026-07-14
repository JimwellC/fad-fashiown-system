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
import os
import re
import time
import hmac
import hashlib
import threading
from datetime import datetime

import requests as req
from flask import Blueprint, jsonify, current_app, request
from flask_login import login_required, current_user

from database import db
from auth.models import Client, Order
from fb_defaults import DEFAULT_FB_TEMPLATE

facebook = Blueprint('facebook', __name__)


@facebook.before_request
def _block_until_password_changed():
    """Match the api/dashboard blueprints: a client forced to change their
    password must not be able to drive Facebook detection with a stale session."""
    if current_user.is_authenticated and \
       not current_user.is_admin and \
       getattr(current_user, 'must_change_password', False):
        return jsonify({"error": "Password change required"}), 403

# ── Graph API config (validate/bump when testing against the dev Page) ──
GRAPH_API_VERSION = 'v21.0'
GRAPH_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'
POLL_INTERVAL_SECONDS = 3        # live-comments poll cadence (SSE is a later option)
COMMENT_PAGE_SIZE = 50           # newest N comments fetched each poll
LIVE_RECHECK_POLLS = 10          # re-check the live video every ~30s (end / new live)
SEND_RETRY_DELAY_SECONDS = 30    # per handoff: retry once after 30s, then fail
HTTP_TIMEOUT = 15
# Fallback buyer keywords — MUST match the TikTok default (dashboard.client_settings)
# so a comment gets the same green highlight on either platform.
DEFAULT_KEYWORDS = 'mine,ako,akin,ko,me,samin'

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
    """Return the newest comments for a live video (expected shape:
    {id, from:{id,name}, message, created_time}).

    order=reverse_chronological puts the NEWEST comments first, so new comments
    always land on page 1. Without this, Graph defaults to the oldest 25 and the
    same stale page is returned forever once a live passes 25 comments — the
    console would silently stop seeing new buyers.
    """
    try:
        r = req.get(
            f'{GRAPH_BASE}/{live_video_id}/comments',
            params={
                'fields': 'id,from,message,created_time',
                'order': 'reverse_chronological',
                'limit': COMMENT_PAGE_SIZE,
                'access_token': token,
            },
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
    polls_since_recheck = 0

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
                        (client.custom_keywords or DEFAULT_KEYWORDS).split(',') if k.strip()]

        # (Re)discover the Page's current LIVE broadcast. We re-check periodically
        # so we notice a live that ENDED (stop polling a dead video) or a NEW live
        # that started — otherwise we'd poll the first video's stale comments forever.
        if not live_video_id or polls_since_recheck >= LIVE_RECHECK_POLLS:
            polls_since_recheck = 0
            current = _resolve_live_video_id(page_id, token)
            if current != live_video_id:
                if current:
                    print(f'FB: watching live video {current}')
                    seen.clear()   # new broadcast → fresh dedup set
                live_video_id = current
        polls_since_recheck += 1

        if not live_video_id:
            # Nothing live yet (Start can be pressed before going live). Keep waiting.
            stop.wait(POLL_INTERVAL_SECONDS)
            continue

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
    # Flush pending batches in the BACKGROUND so the Stop request returns
    # immediately. A failed send (e.g. expired token) otherwise blocks ~60s each
    # (15s attempt + 30s retry sleep + 15s retry), and batches flush one by one —
    # a live with several buyers could hang the request for minutes.
    if socketio_ref is not None:
        socketio_ref.start_background_task(flush_pending_for_client, app, client_id)
    else:
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
    # Key the batch on the buyer's STABLE Facebook user id (stored in buyer_psid,
    # taken from the comment's from.id), NOT the display name — two different
    # buyers can share a name, which would merge them into one wrong message.
    buyer_key = order.buyer_psid or f'name:{order.buyer_username}'
    delay = (client.fb_message_delay or 4) * 60

    with _pending_lock:
        by_buyer = _pending.setdefault(client.id, {})
        entry = by_buyer.get(buyer_key)
        if entry and entry.get('timer'):
            entry['timer'].cancel()          # reset window on each new win
        if not entry:
            entry = {'timer': None, 'order_ids': [], 'comment_id': None,
                     'psid': None, 'buyer_name': order.buyer_username}
            by_buyer[buyer_key] = entry

        entry['order_ids'].append(order.id)
        entry['buyer_name'] = order.buyer_username      # latest display name (for the toast)
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
                'buyer': entry.get('buyer_name', 'buyer'),
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


def recover_pending_batches(app):
    """Re-queue Facebook orders whose auto-message never sent (e.g. the worker
    restarted mid batch-window). In-memory timers don't survive a restart, so
    without this a redeploy silently drops the buyer's message.

    OPT-IN via FB_RECOVER_ON_BOOT=1 so that merely importing the app (management
    scripts, tests, the local runner) never fires real Facebook sends.
    """
    import os
    if os.getenv('FB_RECOVER_ON_BOOT') != '1':
        return
    count = 0
    with app.app_context():
        pending = Order.query.filter(
            Order.platform == 'facebook',
            Order.message_sent.is_(False),
            Order.message_failed.is_(False),
        ).all()
        by_client = {}
        for o in pending:
            by_client.setdefault(o.client_id, []).append(o)
        for client_id, orders in by_client.items():
            client = db.session.get(Client, client_id)
            if not (client and client.fb_auto_message_enabled
                    and client.facebook_page_token):
                continue
            for o in orders:
                schedule_message_for_order(app, client, o)
                count += 1
    if count:
        print(f'FB: re-queued {count} pending auto-message order(s) after restart')


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

    # Fallback: Send API by PSID. NOTE: a live comment's from.id is generally NOT
    # a messaging PSID, so this rarely succeeds today — it exists for the future
    # webhook-sourced PSID path. Keep the primary (private_replies) error if this
    # also fails, since that's the actionable one.
    primary_err = err
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
        except Exception:
            pass

    return False, primary_err


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


# ──────────────────────────────────────────────────────────────────────────
#  Webhook receiver (public) — the Live Video API `live_videos` read endpoint
#  is gated behind App Review (error #10). Page `feed` webhooks deliver comment
#  events using only pages_read_engagement + pages_manage_metadata, which avoids
#  that gate. Facebook pushes here; we emit to the seller's dashboard room —
#  same downstream flow as the polling consumer, no polling, real-time.
# ──────────────────────────────────────────────────────────────────────────
def subscribe_page_to_feed(client):
    """Subscribe the client's Page to 'feed' webhooks so Facebook pushes comment
    events to /webhooks/facebook. Best-effort; returns (ok, error)."""
    if not (client.facebook_page_id and client.facebook_page_token):
        return False, 'no page/token'
    try:
        r = req.post(
            f'{GRAPH_BASE}/{client.facebook_page_id}/subscribed_apps',
            params={'access_token': client.facebook_page_token},
            data={'subscribed_fields': 'feed'},
            timeout=HTTP_TIMEOUT,
        )
        body = r.json()
        if r.status_code == 200 and body.get('success'):
            return True, None
        return False, body.get('error', {}).get('message', r.text)
    except Exception as e:
        return False, str(e)


def _verify_webhook_signature(payload_bytes, header):
    """Verify Facebook's X-Hub-Signature-256 (HMAC-SHA256 of the raw body with
    the App Secret). If FB_APP_SECRET isn't configured we skip (dev only)."""
    app_secret = os.getenv('FB_APP_SECRET', '')
    if not app_secret:
        return True  # not configured — dev/test; can't verify
    if not header or not header.startswith('sha256='):
        return False
    expected = 'sha256=' + hmac.new(
        app_secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


@facebook.route('/webhooks/facebook', methods=['GET'])
def facebook_webhook_verify():
    """Facebook's subscription handshake: echo hub.challenge if the token matches."""
    verify_token = os.getenv('FB_WEBHOOK_VERIFY_TOKEN', '')
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge', '')
    if mode == 'subscribe' and verify_token and token == verify_token:
        return challenge, 200
    return 'Forbidden', 403


@facebook.route('/webhooks/facebook', methods=['POST'])
def facebook_webhook_receive():
    """Receive Page 'feed' events and push comment activity to the seller's
    dashboard. Always returns 200 (except a bad signature) so Facebook doesn't
    retry/disable the subscription."""
    raw = request.get_data()
    if not _verify_webhook_signature(raw, request.headers.get('X-Hub-Signature-256')):
        return 'Bad signature', 403

    try:
        data = request.get_json(silent=True) or {}
        if data.get('object') != 'page':
            return '', 200

        for entry in data.get('entry', []):
            page_id = str(entry.get('id', ''))
            client = Client.query.filter_by(facebook_page_id=page_id).first()
            # Only surface comments for a client who has FB messaging enabled.
            if not client or not client.fb_auto_message_enabled:
                continue

            mode = client.detection_mode or 'keywords'
            keywords = [k.strip().lower() for k in
                        (client.custom_keywords or DEFAULT_KEYWORDS).split(',') if k.strip()]

            for change in entry.get('changes', []):
                if change.get('field') != 'feed':
                    continue
                value = change.get('value', {}) or {}
                if value.get('item') != 'comment' or value.get('verb') != 'add':
                    continue

                frm = value.get('from', {}) or {}
                from_id = str(frm.get('id', '')) if frm.get('id') else None
                # Ignore the Page's own comments (the seller replying).
                if from_id and from_id == page_id:
                    continue

                comment_id = value.get('comment_id') or value.get('id')
                message = value.get('message', '') or ''
                username = frm.get('name') or 'Facebook User'

                if socketio_ref:
                    socketio_ref.emit('new_comment', {
                        'username': username,
                        'message': message,
                        'is_buyer': _is_buyer(message, mode, keywords),
                        'platform': 'facebook',
                        'comment_id': comment_id,
                        'from_id': from_id,
                    }, room=f'client_{client.id}')
    except Exception as e:
        # Never fail the webhook — Facebook disables endpoints that error.
        print(f'FB webhook error: {e}')

    return '', 200
