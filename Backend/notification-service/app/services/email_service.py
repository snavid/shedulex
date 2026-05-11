from flask import current_app
from flask_mail import Message
from app.extensions import mail


def send_email(to: str, subject: str, body: str, html: bool = False) -> bool:
    try:
        msg = Message(subject=subject, recipients=[to])
        if html:
            msg.html = body
        else:
            msg.body = body
        mail.send(msg)
        return True
    except Exception as exc:
        current_app.logger.error(f"Email failed to {to}: {exc}")
        return False
