# auth/routes.py
# Login, logout - Registration is ADMIN ONLY (invite only)

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime
from database import db
from auth.models import Client
from flask_limiter import Limiter


auth = Blueprint('auth', __name__)


# ── ADMIN REQUIRED DECORATOR ──
def admin_required(f):
    """Only allow admin users to access this route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function


# ── LOGIN ──
@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Max 10 login attempts per minute
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = request.form.get('remember', False)

        client = Client.query.filter_by(email=email).first()

        if not client or not client.check_password(password):
            flash('Invalid email or password', 'error')
            return render_template('login.html')

        if not client.is_active:
            flash('Account deactivated. Contact support.', 'error')
            return render_template('login.html')

        login_user(client, remember=remember)
        client.last_login = datetime.utcnow()
        db.session.commit()

        print(f"✅ Login: {client.business_name} (Admin: {client.is_admin})")

        # Admins go to admin panel, clients go to dashboard
        if client.is_admin:
            return redirect(url_for('auth.admin_panel'))

        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))

    return render_template('login.html')


# ── LOGOUT ──
@auth.route('/logout')
@login_required
def logout():
    name = current_user.business_name
    logout_user()
    print(f"👋 Logout: {name}")
    return redirect(url_for('auth.login'))


# ══════════════════════════════════════
# ADMIN PANEL - Only you can access this
# ══════════════════════════════════════

@auth.route('/admin')
@admin_required
def admin_panel():
    """Admin dashboard - manage all clients"""
    clients = Client.query.filter_by(is_admin=False).order_by(
        Client.created_at.desc()
    ).all()
    return render_template('admin.html', clients=clients)


@auth.route('/admin/create-client', methods=['POST'])
@admin_required
def create_client():
    """Create a new client account (admin only)"""
    business_name = request.form.get('business_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    plan = request.form.get('plan', 'basic')

    # Validate
    if not business_name or not email or not password:
        flash('All fields are required', 'error')
        return redirect(url_for('auth.admin_panel'))

    if len(password) < 6:
        flash('Password must be at least 6 characters', 'error')
        return redirect(url_for('auth.admin_panel'))

    existing = Client.query.filter_by(email=email).first()
    if existing:
        flash(f'Email already registered: {email}', 'error')
        return redirect(url_for('auth.admin_panel'))

    # Create client
    client = Client(
        business_name=business_name,
        email=email,
        plan=plan,
        is_admin=False
    )
    client.set_password(password)

    db.session.add(client)
    db.session.commit()

    print(f"✅ Admin created client: {business_name} ({email})")
    flash(f'✅ Account created for {business_name}!', 'success')
    return redirect(url_for('auth.admin_panel'))


@auth.route('/admin/toggle-client/<int:client_id>', methods=['POST'])
@admin_required
def toggle_client(client_id):
    """Activate or deactivate a client account"""
    client = Client.query.get_or_404(client_id)

    if client.is_admin:
        flash('Cannot modify admin accounts', 'error')
        return redirect(url_for('auth.admin_panel'))

    client.is_active = not client.is_active
    db.session.commit()

    status = 'activated' if client.is_active else 'deactivated'
    flash(f'Account {status}: {client.business_name}', 'success')
    return redirect(url_for('auth.admin_panel'))


@auth.route('/admin/delete-client/<int:client_id>', methods=['POST'])
@admin_required
def delete_client(client_id):
    """Delete a client account"""
    client = Client.query.get_or_404(client_id)

    if client.is_admin:
        flash('Cannot delete admin accounts', 'error')
        return redirect(url_for('auth.admin_panel'))

    business_name = client.business_name
    db.session.delete(client)
    db.session.commit()

    flash(f'Account deleted: {business_name}', 'success')
    return redirect(url_for('auth.admin_panel'))


@auth.route('/admin/reset-password/<int:client_id>', methods=['POST'])
@admin_required
def reset_password(client_id):
    """Reset a client's password"""
    client = Client.query.get_or_404(client_id)
    new_password = request.form.get('new_password', '').strip()

    if len(new_password) < 6:
        flash('Password must be at least 6 characters', 'error')
        return redirect(url_for('auth.admin_panel'))

    client.set_password(new_password)
    db.session.commit()

    flash(f'Password reset for: {client.business_name}', 'success')
    return redirect(url_for('auth.admin_panel'))


# ── BLOCK PUBLIC REGISTRATION ──
@auth.route('/register')
def register():
    """Registration is disabled - admin creates accounts"""
    flash('Account registration is by invitation only. Contact admin.', 'error')
    return redirect(url_for('auth.login'))