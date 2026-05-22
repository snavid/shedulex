from flask import current_app, render_template_string
from flask_mail import Message
from app.extensions import mail


_VERIFY_TEMPLATE = """
<h2>Welcome to Shedulex!</h2>
<p>Hi {{ name }},</p>
<p>Please verify your email by clicking the link below:</p>
<a href="{{ url }}">Verify Email</a>
<p>This link expires in 24 hours.</p>
"""

_RESET_TEMPLATE = """
<h2>Password Reset Request</h2>
<p>Hi {{ name }},</p>
<p>Click the link below to reset your password:</p>
<a href="{{ url }}">Reset Password</a>
<p>This link expires in 1 hour. If you did not request this, ignore this email.</p>
"""

_CREDENTIALS_TEMPLATE = """
<h2>Welcome to Shedulex — Your Lecturer Account</h2>
<p>Hi {{ name }},</p>
<p>An account has been created for you on the Shedulex academic scheduling platform.</p>
<table style="border-collapse:collapse;font-family:monospace;">
  <tr><td style="padding:4px 12px;"><strong>Login URL</strong></td><td>{{ login_url }}</td></tr>
  <tr><td style="padding:4px 12px;"><strong>Username</strong></td><td>{{ username }}</td></tr>
  <tr><td style="padding:4px 12px;"><strong>Password</strong></td><td>{{ password }}</td></tr>
</table>
<p style="color:#c0392b;"><strong>You will be required to change your password on first login.</strong></p>
<p>If you did not expect this email, please contact your department administrator.</p>
"""


def send_verification_email(to: str, name: str, token: str):
    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173")
    verify_url = f"{frontend_url}/verify-email?token={token}"
    body = render_template_string(_VERIFY_TEMPLATE, name=name, url=verify_url)
    _send(to=to, subject="Verify your Shedulex account", html_body=body)


def send_password_reset_email(to: str, name: str, token: str):
    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173")
    reset_url = f"{frontend_url}/reset-password?token={token}"
    body = render_template_string(_RESET_TEMPLATE, name=name, url=reset_url)
    _send(to=to, subject="Reset your Shedulex password", html_body=body)


def send_lecturer_credentials_email(to: str, name: str, username: str, password: str):
    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173")
    login_url = f"{frontend_url}/login"
    body = render_template_string(
        _CREDENTIALS_TEMPLATE,
        name=name,
        login_url=login_url,
        username=username,
        password=password,
    )
    _send(to=to, subject="Your Shedulex Lecturer Account Credentials", html_body=body)


def _send(to: str, subject: str, html_body: str):
    try:
        msg = Message(subject=subject, recipients=[to], html=html_body)
        mail.send(msg)
    except Exception as exc:
        current_app.logger.error(f"Failed to send email to {to}: {exc}")
