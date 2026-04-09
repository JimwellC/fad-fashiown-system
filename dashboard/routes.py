# dashboard/routes.py
from flask import Blueprint, render_template, request, make_response, redirect, url_for
from flask_login import login_required, current_user
from database import db
from auth.models import Order
from datetime import datetime
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