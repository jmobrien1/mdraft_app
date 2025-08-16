"""
Authentication routes for the mdraft application.

This module provides login, logout, registration, and email verification
functionality with enhanced security features including password validation,
rate limiting, and session management.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import uuid

from ..models import User, EmailVerificationToken
from .. import db, limiter
from ..config import get_config
from ..utils.password import validate_password_strength
from ..utils.rate_limiting import create_auth_rate_limiter, get_client_ip, get_login_rate_limit_key
from ..utils.session import rotate_session, invalidate_other_sessions
from .allowlist import is_email_allowed
from .visitor import rotate_visitor_session

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("LOGIN_RATE_LIMIT", "10 per minute"), 
               key_func=lambda: get_login_rate_limit_key())
def login():
    """Handle user login with rate limiting and security features."""
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
        
        # Initialize rate limiter
        config = get_config()
        rate_limiter = create_auth_rate_limiter(config)
        client_ip = get_client_ip()
        
        # Check rate limiting for both username and IP
        username_allowed, username_message = rate_limiter.check_auth_attempt(email, "username")
        ip_allowed, ip_message = rate_limiter.check_auth_attempt(client_ip, "ip")
        
        if not username_allowed:
            flash(username_message, "error")
            return render_template("auth/login.html"), 423  # Locked
        
        if not ip_allowed:
            flash(ip_message, "error")
            return render_template("auth/login.html"), 423  # Locked
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active and not user.revoked:
            # Check email verification requirement
            if config.security.EMAIL_VERIFICATION_REQUIRED and not user.email_verified:
                flash("Please verify your email address before logging in. Check your inbox for a verification link.", "error")
                return render_template("auth/login.html"), 403
            
            # Record successful login (clears failure counters)
            rate_limiter.record_successful_attempt(email, "username")
            rate_limiter.record_successful_attempt(client_ip, "ip")
            
            # Create response object for cookie manipulation
            response = make_response()
            
            # Rotate visitor session ID for security
            rotate_visitor_session(response)
            
            # Rotate session for security
            rotate_session()
            
            # Log in the user
            login_user(user, remember=remember)
            
            # Invalidate other sessions if single session mode is enabled
            if config.security.AUTH_SINGLE_SESSION:
                invalidate_other_sessions(user.id)
            
            # Update user's last login timestamp
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get("next")
            if not next_page or not next_page.startswith("/"):
                next_page = url_for("ui.index")
            
            # Redirect with the response containing the rotated cookie
            response.headers['Location'] = next_page
            response.status_code = 302
            return response
        else:
            # Record failed attempt
            rate_limiter.record_failed_attempt(email, "username")
            rate_limiter.record_failed_attempt(client_ip, "ip")
            
            # Get remaining attempts for user feedback
            remaining_username = rate_limiter.get_remaining_attempts(email, "username")
            remaining_ip = rate_limiter.get_remaining_attempts(client_ip, "ip")
            remaining = min(remaining_username, remaining_ip)
            
            if remaining == 0:
                flash("Account temporarily locked due to too many failed attempts. Please try again later.", "error")
                return render_template("auth/login.html"), 423
            elif remaining <= 2:
                flash(f"Invalid email or password. {remaining} attempts remaining before lockout.", "error")
            else:
                flash("Invalid email or password", "error")
            
            return render_template("auth/login.html"), 401
    
    return render_template("auth/login.html")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():
    """Handle user registration with password validation and email verification."""
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
        
        # Validate password strength
        config = get_config()
        password_validation = validate_password_strength(password, config)
        
        if not password_validation:
            # Display specific password errors
            for error in password_validation.errors:
                flash(error, "error")
            
            # Display warnings as info messages
            for warning in password_validation.warnings:
                flash(warning, "info")
            
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
        user = User(
            email=email, 
            revoked=False,
            email_verified=not config.security.EMAIL_VERIFICATION_REQUIRED  # Auto-verify if not required
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Create email verification token if required
        if config.security.EMAIL_VERIFICATION_REQUIRED:
            token = EmailVerificationToken(
                user_id=user.id,
                token=str(uuid.uuid4()),
                expires_at=datetime.utcnow() + timedelta(hours=config.security.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)
            )
            db.session.add(token)
            db.session.commit()
            
            # TODO: Send verification email here
            # For now, we'll just show a message
            flash("Account created successfully! Please check your email for a verification link.", "info")
            return render_template("auth/register.html"), 200
        
        # Create response object for cookie manipulation
        response = make_response()
        
        # Rotate visitor session ID for security
        rotate_visitor_session(response)
        
        # Rotate session for security
        rotate_session()
        
        # Log in the new user
        login_user(user)
        flash("Account created successfully! Welcome to mdraft.", "info")
        
        next_page = request.args.get("next")
        if not next_page or not next_page.startswith("/"):
            next_page = url_for("ui.index")
        
        # Redirect with the response containing the rotated cookie
        response.headers['Location'] = next_page
        response.status_code = 302
        return response
    
    return render_template("auth/register.html")


@bp.route("/logout")
@login_required
def logout():
    """Handle user logout with session cleanup."""
    logout_user()
    flash("You have been logged out", "info")
    return redirect(url_for("ui.index"))


@bp.route("/verify/<token>")
def verify_email(token):
    """Handle email verification."""
    # Find the verification token
    verification_token = EmailVerificationToken.query.filter_by(
        token=token,
        used=False
    ).first()
    
    if not verification_token:
        flash("Invalid or expired verification link.", "error")
        return redirect(url_for("auth.login"))
    
    # Check if token is expired
    if verification_token.expires_at < datetime.utcnow():
        flash("Verification link has expired. Please request a new one.", "error")
        return redirect(url_for("auth.login"))
    
    # Mark token as used
    verification_token.used = True
    
    # Mark user as verified
    user = verification_token.user
    user.email_verified = True
    
    db.session.commit()
    
    flash("Email verified successfully! You can now log in.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/resend-verification", methods=["GET", "POST"])
@limiter.limit("3 per hour")
def resend_verification():
    """Handle resending email verification."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        
        if not email:
            flash("Email is required", "error")
            return render_template("auth/resend_verification.html"), 400
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Don't reveal if user exists or not
            flash("If an account with this email exists, a verification link has been sent.", "info")
            return render_template("auth/resend_verification.html"), 200
        
        if user.email_verified:
            flash("This email is already verified.", "info")
            return render_template("auth/resend_verification.html"), 200
        
        config = get_config()
        
        # Create new verification token
        token = EmailVerificationToken(
            user_id=user.id,
            token=str(uuid.uuid4()),
            expires_at=datetime.utcnow() + timedelta(hours=config.security.EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS)
        )
        db.session.add(token)
        db.session.commit()
        
        # TODO: Send verification email here
        flash("If an account with this email exists, a verification link has been sent.", "info")
        return render_template("auth/resend_verification.html"), 200
    
    return render_template("auth/resend_verification.html")
