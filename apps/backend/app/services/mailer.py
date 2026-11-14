"""Email delivery helpers for verification and reset codes."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings


def smtp_configured() -> bool:
    return bool(
        settings.smtp_host
        and settings.smtp_port
        and settings.smtp_user
        and settings.smtp_password
        and settings.email_from
    )


def demo_mode_active() -> bool:
    return (not smtp_configured()) and bool(settings.demo_mode)


def _build_message(purpose: str, email: str, code: str) -> EmailMessage:
    subject = "Your verification code" if purpose == "verify" else "Your password reset code"
    heading = "Confirm your email" if purpose == "verify" else "Reset your password"
    intro = (
        "Use the code below to verify your email and continue."
        if purpose == "verify"
        else "Use the code below to reset your password."
    )
    body = (
        f"{heading}\n\n"
        f"{intro}\n\n"
        f"Code: {code}\n"
        "This code expires in 10 minutes.\n"
        "If you did not request this, you can ignore this email."
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#1f2937;">
      <h2 style="margin-bottom:8px;">{heading}</h2>
      <p style="margin:0 0 16px;">{intro}</p>
      <div style="font-size:28px;font-weight:700;letter-spacing:6px;padding:16px 20px;border:1px dashed #94a3b8;border-radius:12px;display:inline-block;background:#f8fafc;">
        {code}
      </div>
      <p style="margin-top:16px;color:#475569;font-size:14px;">This code expires in 10 minutes.</p>
      <p style="margin-top:8px;color:#64748b;font-size:13px;">If you did not request this, you can ignore this email.</p>
    </div>
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.email_from or "no-reply@example.com"
    msg["To"] = email
    msg.set_content(body)
    msg.add_alternative(html, subtype="html")
    return msg


def send_code(purpose: str, email: str, code: str) -> dict[str, object]:
    if not smtp_configured():
        if demo_mode_active():
            return {"delivered": False, "demoCode": code}
        return {"delivered": False}

    try:
        msg = _build_message(purpose, email, code)
        port = int(settings.smtp_port or 587)
        if port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, port, timeout=15) as server:
                server.login(settings.smtp_user or "", settings.smtp_password or "")
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, port, timeout=15) as server:
                server.starttls()
                server.login(settings.smtp_user or "", settings.smtp_password or "")
                server.send_message(msg)
        return {"delivered": True}
    except Exception:
        return {"delivered": False}
