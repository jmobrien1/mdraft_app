"""
Authentication routes for the mdraft application.

This module provides login and logout functionality using Flask-Login.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from ..models import User
from .. import db, limiter
from .allowlist import is_email_allowed

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for("ui.index"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember", "false").lower() == "true"
        
        if not email or not password:
            flash("Email and password are required", "error")
            return render_template("auth/login.html"), 400
        
        # Check if email is allowed (invite-only beta)
        if not is_email_allowed(email):
            flash("This email is not authorized for beta access. Please contact support for an invitation.", "error")
            return render_template("auth/login.html"), 403
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active and not user.revoked:
            login_user(user, remember=remember)
            next_page = request.args.get("next")
            if not next_page or not next_page.startswith("/"):
                next_page = url_for("ui.index")
            return redirect(next_page)
        else:
            flash("Invalid email or password", "error")
            return render_template("auth/login.html"), 401
    
    return render_template("auth/login.html")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for("ui.index"))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        if not email or not password:
            flash("Email and password are required", "error")
            return render_template("auth/register.html"), 400
        
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("auth/register.html"), 400
        
        if len(password) < 8:
            flash("Password must be at least 8 characters long", "error")
            return render_template("auth/register.html"), 400
        
        # Check if email is allowed (invite-only beta)
        if not is_email_allowed(email):
            flash("This email is not authorized for beta access. Please contact support for an invitation.", "error")
            return render_template("auth/register.html"), 403
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email already exists. Please log in instead.", "error")
            return render_template("auth/register.html"), 409
        
        # Create new user
        user = User(email=email, revoked=False)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Log in the new user
        login_user(user)
        flash("Account created successfully! Welcome to mdraft.", "info")
        
        next_page = request.args.get("next")
        if not next_page or not next_page.startswith("/"):
            next_page = url_for("ui.index")
        return redirect(next_page)
    
    return render_template("auth/register.html")


@bp.route("/logout")
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash("You have been logged out", "info")
    return redirect(url_for("ui.index"))
