# dashboard/routes.py
from flask import Blueprint, render_template, request, make_response, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from database import db
from auth.models import Order
from datetime import datetime, timedelta
import csv
import io

dashboard = Blueprint('dashboard', __name__)


@dashboard.route('/')
@login_required
def index():
    """Main dashboard - redirect admin to admin panel"""
    if current_user.is_admin:
        return redirect(url_for('auth.admin_panel'))
    return render_template(
        'dashboard.html',
        client=current_user,
        business_name=current_user.business_name
    )


@dashboard.route('/orders')
@login_required
def orders():
    """Full order history page - clients only"""
    if current_user.is_admin:
        return redirect(url_for('auth.admin_panel'))

    search = request.args.get('search', '').strip()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = Order.query.filter_by(client_id=current_user.id)

    if search:
        query = query.filter(
            Order.buyer_username.ilike(f'%{search}%') |
            Order.item_name.ilike(f'%{search}%')
        )

    if date_from:
        try:
            query = query.filter(
                Order.timestamp >= datetime.strptime(date_from, '%Y-%m-%d')
            )
        except ValueError:
            pass

    if date_to:
        try:
            query = query.filter(
                Order.timestamp <= datetime.strptime(date_to, '%Y-%m-%d')
            )
        except ValueError:
            pass

    all_orders = Order.query.filter_by(client_id=current_user.id).all()
    total_orders = len(all_orders)
    total_sales = sum(o.price for o in all_orders)

    orders_paginated = query.order_by(
        Order.timestamp.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'orders.html',
        orders=orders_paginated,
        search=search,
        date_from=date_from,
        date_to=date_to,
        total_orders=total_orders,
        total_sales=total_sales,
        business_name=current_user.business_name
    )


@dashboard.route('/orders/export')
@login_required
def export_orders():
    """Export orders to CSV"""
    if current_user.is_admin:
        return redirect(url_for('auth.admin_panel'))

    orders = Order.query.filter_by(
        client_id=current_user.id
    ).order_by(Order.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Order ID', 'Buyer Username', 'Item Name',
        'Price', 'Date & Time', 'Label Printed'
    ])

    for order in orders:
        writer.writerow([
            order.id,
            order.buyer_username,
            order.item_name,
            f'₱{order.price:.2f}',
            order.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Yes' if order.label_printed else 'No'
        ])

    output.seek(0)
    filename = f"orders_{current_user.business_name}_{datetime.now().strftime('%Y%m%d')}.csv"

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


@dashboard.route('/analytics')
@login_required
def analytics():
    """Analytics page - sales insights"""
    if current_user.is_admin:
        return redirect(url_for('auth.admin_panel'))

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=now.weekday())

    all_orders = Order.query.filter_by(client_id=current_user.id).all()

    # ── TODAY ──
    today_orders = [o for o in all_orders if o.timestamp >= today_start]
    today_count = len(today_orders)
    today_revenue = sum(o.price for o in today_orders)

    # ── THIS WEEK ──
    week_orders = [o for o in all_orders if o.timestamp >= week_start]
    week_count = len(week_orders)
    week_revenue = sum(o.price for o in week_orders)

    # ── THIS MONTH ──
    month_orders = [o for o in all_orders if o.timestamp >= month_start]
    month_count = len(month_orders)
    month_revenue = sum(o.price for o in month_orders)

    # ── ALL TIME ──
    total_count = len(all_orders)
    total_revenue = sum(o.price for o in all_orders)
    avg_order = total_revenue / total_count if total_count > 0 else 0

    # ── TOP BUYERS ──
    buyer_counts = {}
    buyer_totals = {}
    for o in all_orders:
        buyer_counts[o.buyer_username] = buyer_counts.get(o.buyer_username, 0) + 1
        buyer_totals[o.buyer_username] = buyer_totals.get(o.buyer_username, 0) + o.price

    all_top_buyers = sorted(
        buyer_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    top_buyers_full = [
        {
            'username': username,
            'orders': count,
            'total': buyer_totals[username]
        }
        for username, count in all_top_buyers
    ]

    # Paginate buyers
    buyers_page = request.args.get('buyers_page', 1, type=int)
    buyers_per_page = 5
    buyers_total = len(top_buyers_full)
    buyers_pages = (buyers_total + buyers_per_page - 1) // buyers_per_page
    buyers_start = (buyers_page - 1) * buyers_per_page
    buyers_end = buyers_start + buyers_per_page
    top_buyers_data = top_buyers_full[buyers_start:buyers_end]
    top_buyers_max = top_buyers_full[0]['orders'] if top_buyers_full else 1

    # ── TOP ITEMS ──
    item_counts = {}
    item_totals = {}
    for o in all_orders:
        item_counts[o.item_name] = item_counts.get(o.item_name, 0) + 1
        item_totals[o.item_name] = item_totals.get(o.item_name, 0) + o.price

    all_top_items = sorted(
        item_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )

    top_items_full = [
        {
            'name': name,
            'orders': count,
            'total': item_totals[name]
        }
        for name, count in all_top_items
    ]

    # Paginate items
    items_page = request.args.get('items_page', 1, type=int)
    items_per_page = 5
    items_total = len(top_items_full)
    items_pages = (items_total + items_per_page - 1) // items_per_page
    items_start = (items_page - 1) * items_per_page
    items_end = items_start + items_per_page
    top_items_data = top_items_full[items_start:items_end]
    top_items_max = top_items_full[0]['orders'] if top_items_full else 1

    # ── DAILY SALES (Last 7 days) ──
    daily_data = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        day_orders = [
            o for o in all_orders
            if day_start <= o.timestamp <= day_end
        ]
        daily_data.append({
            'label': day.strftime('%a'),
            'date': day.strftime('%b %d'),
            'count': len(day_orders),
            'revenue': sum(o.price for o in day_orders)
        })

    # ── MONTHLY SALES (Last 6 months) ──
    monthly_data = []
    for i in range(5, -1, -1):
        month_date = now - timedelta(days=i * 30)
        m_start = month_date.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if i == 0:
            m_end = now
        else:
            next_month = m_start.replace(month=m_start.month % 12 + 1) \
                if m_start.month < 12 \
                else m_start.replace(year=m_start.year + 1, month=1)
            m_end = next_month - timedelta(seconds=1)

        m_orders = [
            o for o in all_orders
            if m_start <= o.timestamp <= m_end
        ]
        monthly_data.append({
            'label': month_date.strftime('%b'),
            'count': len(m_orders),
            'revenue': sum(o.price for o in m_orders)
        })

    return render_template(
    'analytics.html',
    today_count=today_count,
    today_revenue=today_revenue,
    week_count=week_count,
    week_revenue=week_revenue,
    month_count=month_count,
    month_revenue=month_revenue,
    total_count=total_count,
    total_revenue=total_revenue,
    avg_order=avg_order,
    top_buyers=top_buyers_data,
    top_buyers_max=top_buyers_max,
    buyers_page=buyers_page,
    buyers_pages=buyers_pages,
    buyers_total=buyers_total,
    top_items=top_items_data,
    top_items_max=top_items_max,
    items_page=items_page,
    items_pages=items_pages,
    items_total=items_total,
    daily_data=daily_data,
    monthly_data=monthly_data,
    business_name=current_user.business_name
)

@dashboard.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Client settings page"""
    if current_user.is_admin:
        return redirect(url_for('auth.admin_panel'))

    if request.method == 'POST':
        detection_mode = request.form.get('detection_mode', 'keywords')
        custom_keywords = request.form.get('custom_keywords', '').strip()
        highlight_numbers = request.form.get('highlight_numbers') == 'on'

        # Label settings
        label_title = request.form.get('label_title', '').strip()
        label_tagline = request.form.get('label_tagline', '').strip()
        label_template = request.form.get('label_template', 'classic')
        label_show_order_id = request.form.get('label_show_order_id') == 'on'
        label_show_datetime = request.form.get('label_show_datetime') == 'on'

        current_user.detection_mode = detection_mode
        current_user.custom_keywords = custom_keywords
        current_user.highlight_numbers = highlight_numbers
        current_user.label_title = label_title or 'FAD FASHIOWN'
        current_user.label_tagline = label_tagline or 'Live Selling'
        current_user.label_template = label_template
        current_user.label_show_order_id = label_show_order_id
        current_user.label_show_datetime = label_show_datetime

        db.session.commit()
        flash('Settings saved!', 'success')
        return redirect(url_for('dashboard.settings'))

    return render_template(
        'settings.html',
        client=current_user,
        business_name=current_user.business_name
    )


@dashboard.route('/api/client-settings', methods=['GET'])
def client_settings():
    """Return settings as JSON - accepts token for Chrome extension"""
    from auth.models import Client

    token = request.args.get('token', '')
    if token:
        client = Client.query.filter_by(token=token).first()
        if not client:
            return jsonify({'error': 'Invalid token'}), 401
    elif current_user.is_authenticated:
        client = current_user
    else:
        return jsonify({'error': 'Unauthorized'}), 401

    return jsonify({
        'detection_mode': client.detection_mode or 'keywords',
        'custom_keywords': client.custom_keywords or 'mine,ako,akin,ko,me,samin',
        'highlight_numbers': client.highlight_numbers or False,
        'label_title': client.label_title or 'FAD FASHIOWN',
        'label_tagline': client.label_tagline or 'Live Selling',
        'label_template': client.label_template or 'classic',
        'label_show_order_id': client.label_show_order_id if client.label_show_order_id is not None else True,
        'label_show_datetime': client.label_show_datetime if client.label_show_datetime is not None else True,
    })

@dashboard.route('/download-my-extension')
@login_required
def download_my_extension():
    """Client downloads their own extension with token pre-embedded"""
    import zipfile
    import io
    import os
    import re
    from datetime import datetime
    from flask import make_response

    client = current_user

    # Generate token if missing
    if not client.token:
        import secrets
        client.token = secrets.token_hex(32)
        db.session.commit()

    # Read extension files
    ext_path = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        '..', 'chrome-extension'
    )

    # Read and update content.js with token
    content_js_path = os.path.join(ext_path, 'content.js')
    with open(content_js_path, 'r') as f:
        content_js = f.read()

    if '__CLIENT_TOKEN__' in content_js:
        content_js_with_token = content_js.replace('__CLIENT_TOKEN__', client.token)
    else:
        content_js_with_token = re.sub(
            r"const CLIENT_TOKEN = '[^']*'",
            f"const CLIENT_TOKEN = '{client.token}'",
            content_js
        )

    # Build README
    readme = f"""FAD FASHIOWN - LIVE SELLING SYSTEM
Setup Instructions for {client.business_name}
{'=' * 50}

DASHBOARD URL:
https://web-production-1fba.up.railway.app

YOUR LOGIN:
Email: {client.email}

SETUP STEPS:
============

STEP 1 - INSTALL QZ TRAY (for silent printing)
  1. Go to: https://qz.io/download/
  2. Download and install QZ Tray
  3. Run it - icon appears in your taskbar/menu bar

STEP 2 - INSTALL CHROME EXTENSION
  1. Open Google Chrome
  2. Go to: chrome://extensions
  3. Turn ON "Developer mode" (top right toggle)
  4. Click "Load unpacked"
  5. Select the "fad-fashiown-extension" folder
  6. Extension is now installed!

STEP 3 - SET THERMAL PRINTER AS DEFAULT
  Windows: Settings > Printers & Scanners > Set as Default
  Mac: System Settings > Printers > Select your printer

EVERY LIVE SESSION:
===================
1. Make sure QZ Tray is running (taskbar icon)
2. Open dashboard and login
3. Go live on TikTok on the SAME Chrome browser
4. Viewers comment codes (L15, 46, LOCK 11, etc.)
5. Green comments appear on dashboard
6. Click winner comment to set as buyer
7. Type the price → Press ENTER
8. Label prints automatically!

Generated: {datetime.now().strftime('%B %d, %Y')}
"""

    # Create zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('README.txt', readme)
        for filename in os.listdir(ext_path):
            filepath = os.path.join(ext_path, filename)
            if os.path.isfile(filepath):
                if filename == 'content.js':
                    zip_file.writestr(
                        f'fad-fashiown-extension/{filename}',
                        content_js_with_token
                    )
                else:
                    zip_file.write(
                        filepath,
                        f'fad-fashiown-extension/{filename}'
                    )

    zip_buffer.seek(0)

    safe_name = ''.join(
        c for c in client.business_name
        if c.isalnum() or c in (' ', '-', '_')
    ).strip().replace(' ', '_')

    response = make_response(zip_buffer.getvalue())
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = \
        f'attachment; filename=FadFashiown_Extension_{safe_name}.zip'
    return response