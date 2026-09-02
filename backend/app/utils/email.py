import datetime as dt
import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models import SystemSetting
from app.utils.security import decrypt_secret

SMTP_KEYS = {
    "smtp_host", "smtp_port", "smtp_security", "smtp_username", "smtp_password",
    "smtp_sender_email", "smtp_sender_name",
}


def get_settings(db: Session):
    rows = db.query(SystemSetting).filter(SystemSetting.key.in_(SMTP_KEYS)).all()
    data = {r.key: r.value for r in rows}
    if data.get("smtp_password"):
        data["smtp_password"] = decrypt_secret(data["smtp_password"]) or ""
    return data


def send_email(db: Session, recipients: Iterable[str], subject: str, body: str,
               attachments: Optional[list[tuple[str, bytes, str]]] = None):
    cfg = get_settings(db)
    host = (cfg.get("smtp_host") or "").strip()
    port = int(cfg.get("smtp_port") or 587)
    security = (cfg.get("smtp_security") or "starttls").lower()
    username = cfg.get("smtp_username") or ""
    password = cfg.get("smtp_password") or ""
    sender = cfg.get("smtp_sender_email") or username
    sender_name = cfg.get("smtp_sender_name") or sender

    if not host or not sender:
        raise ValueError("SMTP is not configured. Configure SMTP settings first.")

    msg = EmailMessage()
    msg["From"] = f"{sender_name} <{sender}>" if sender_name else sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject or "Lead CRM notification"
    msg.set_content(body or "")

    for filename, content, mime in attachments or []:
        maintype, subtype = (mime.split("/", 1) + ["octet-stream"])[:2]
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    if security == "ssl":
        with smtplib.SMTP_SSL(host, port, timeout=20) as smtp:
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            if security == "starttls":
                smtp.starttls()
                smtp.ehlo()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)


def send_password_reset(db: Session, user, token: str, base_url: str = ""):
    cfg = get_settings(db)
    site_name = (db.query(SystemSetting).filter(SystemSetting.key == "site_name").first())
    app_name = site_name.value if site_name and site_name.value else "Lead CRM"
    frontend_url = (db.query(SystemSetting).filter(SystemSetting.key == "frontend_url").first())
    base = (base_url or (frontend_url.value if frontend_url and frontend_url.value else "")).rstrip("/")
    reset_url = f"{base}/#/reset-password?token={token}" if base else f"/#/reset-password?token={token}"
    subject = f"{app_name} password reset"
    exp_row = db.query(SystemSetting).filter(SystemSetting.key == "password_reset_expire_minutes").first()
    try: expiry = int(exp_row.value) if exp_row and exp_row.value else 30
    except ValueError: expiry = 30
    body = (
        f"Hello {user.full_name},\n\n"
        f"A password reset was requested for your {app_name} account.\n\n"
        f"Use this link to set a new password:\n{reset_url}\n\n"
        f"This link expires in {expiry} minutes and can only be used once. "
        f"If you did not request this, you can ignore this email.\n\n{app_name}"
    )
    send_email(db, [user.email], subject, body)
