# dashboard/routes.py
# Main dashboard route - protected by login

from flask import Blueprint, render_template
from flask_login import login_required, current_user

dashboard = Blueprint('dashboard', __name__)


@dashboard.route('/')
@login_required
def index():
    """Main dashboard - requires login"""
    return render_template(
        'dashboard.html',
        client=current_user,
        business_name=current_user.business_name
    )