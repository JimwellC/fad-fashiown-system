# auth/routes.py
# Login, logout - Registration is ADMIN ONLY (invite only)

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort, make_response
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime
from database import db
from auth.models import Client

auth = Blueprint('auth', __name__)


# ── ADMIN REQUIRED DECORATOR ──
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ── LOGIN ──
@auth.route('/login', methods=['GET', 'POST'])
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

        # Force password change on first login
        if client.must_change_password and not client.is_admin:
            return redirect(url_for('auth.change_password'))

        print(f"✅ Login: {client.business_name}")

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


# ── ADMIN PANEL ──
@auth.route('/admin')
@admin_required
def admin_panel():
    clients = Client.query.filter_by(is_admin=False).order_by(
        Client.created_at.desc()
    ).all()
    return render_template('admin.html', clients=clients)


@auth.route('/admin/create-client', methods=['POST'])
@admin_required
def create_client():
    business_name = request.form.get('business_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    plan = request.form.get('plan', 'basic')

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

    client = Client(
        business_name=business_name,
        email=email,
        plan=plan,
        is_admin=False,
        must_change_password=True
    )
    client.set_password(password)
    db.session.add(client)
    db.session.commit()

    flash(f'✅ Account created for {business_name}!', 'success')
    return redirect(url_for('auth.admin_panel'))


@auth.route('/admin/toggle-client/<int:client_id>', methods=['POST'])
@admin_required
def toggle_client(client_id):
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
    flash('Account registration is by invitation only. Contact admin.', 'error')
    return redirect(url_for('auth.login'))


@auth.route('/admin/download-extension/<int:client_id>')
@admin_required
def download_extension(client_id):
    """Generate and download Chrome extension with client token embedded"""
    import zipfile
    import io
    import os
    import re

    client = Client.query.get_or_404(client_id)

    # Generate token if client doesn't have one
    if not client.token:
        import secrets
        client.token = secrets.token_hex(32)
        db.session.commit()
        print(f"Generated token for {client.business_name}")

    # Read the extension files
    ext_path = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        '..', 'chrome-extension'
    )

    # Read content.js
    content_js_path = os.path.join(ext_path, 'content.js')
    with open(content_js_path, 'r') as f:
        content_js = f.read()

    # Replace placeholder OR existing token with this client's token
    if '__CLIENT_TOKEN__' in content_js:
        content_js_with_token = content_js.replace('__CLIENT_TOKEN__', client.token)
    else:
        content_js_with_token = re.sub(
            r"const CLIENT_TOKEN = '[^']*'",
            f"const CLIENT_TOKEN = '{client.token}'",
            content_js
        )

    # Create readme instructions
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
    3. Run it - you will see its icon in your taskbar

    STEP 2 - INSTALL CHROME EXTENSION
    1. Open Google Chrome
    2. Go to: chrome://extensions
    3. Turn ON "Developer mode" (toggle, top right)
    4. Click "Load unpacked"
    5. Select the "fad-fashiown-extension" folder
    6. You should see "Fad Fashiown" extension added

    STEP 3 - SET THERMAL PRINTER AS DEFAULT
    Windows: Settings > Printers & Scanners > Set as Default
    Mac: System Settings > Printers & Scanners > Select printer

    STEP 4 - CREATE DESKTOP SHORTCUT (optional)
    Bookmark this URL in Chrome for quick access:
    https://web-production-1fba.up.railway.app

    EVERY LIVE SESSION:
    ===================
    1. Make sure QZ Tray is running (taskbar icon)
    2. Open dashboard and login
    3. Go live on TikTok on the SAME Chrome browser
    4. Viewers comment codes (L15, 46, LOCK 11, etc.)
    5. Green comments appear on your dashboard
    6. Click the winner's comment to set as buyer
    7. Type the price
    8. Press ENTER - label prints automatically!

    NEED HELP?
    ==========
    Contact your system provider for support.

    Generated: {datetime.now().strftime('%B %d, %Y')}
    """

    # Create zip in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add README
        zip_file.writestr('README.txt', readme)

        # Add extension files
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

    # Clean business name for filename
    safe_name = ''.join(
        c for c in client.business_name
        if c.isalnum() or c in (' ', '-', '_')
    ).strip().replace(' ', '_')

    filename = f'FadFashiown_Extension_{safe_name}.zip'

    response = make_response(zip_buffer.getvalue())
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response

@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Force password change on first login"""
    if not current_user.must_change_password:
        return redirect(url_for('dashboard.index'))

    error = None
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if len(new_password) < 8:
            error = 'Password must be at least 8 characters'
        elif new_password != confirm_password:
            error = 'Passwords do not match'
        elif not any(c.isupper() for c in new_password):
            error = 'Password must contain at least one uppercase letter'
        elif not any(c.isdigit() for c in new_password):
            error = 'Password must contain at least one number'
        else:
            current_user.set_password(new_password)
            current_user.must_change_password = False
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('dashboard.index'))

    return render_template('change_password.html', error=error)