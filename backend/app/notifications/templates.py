"""Bilingual (Arabic first) transactional email content."""

from __future__ import annotations

from urllib.parse import quote

from app.core.config import get_settings
from app.notifications.email import EmailMessage


def _link(path: str, token: str) -> str:
    return f"{get_settings().frontend_url.rstrip('/')}{path}?token={quote(token)}"


def verification_email(to: str, name: str, token: str, locale: str) -> EmailMessage:
    link = _link("/verify-email", token)
    hours = get_settings().email_verification_ttl_hours
    if locale == "en":
        subject = "Confirm your email address"
        text = (
            f"Hello {name},\n\nPlease confirm your email address by opening this link:\n"
            f"{link}\n\nThe link expires in {hours} hours. "
            "If you did not create an account, ignore this message."
        )
    else:
        subject = "تأكيد بريدك الإلكتروني"
        text = (
            f"مرحباً {name}،\n\nيرجى تأكيد بريدك الإلكتروني بفتح الرابط التالي:\n{link}\n\n"
            f"ينتهي الرابط خلال {hours} ساعة. إذا لم تقم بإنشاء حساب، تجاهل هذه الرسالة."
        )
    return EmailMessage(to=to, subject=subject, text=text, tags=("email_verify",))


def password_reset_email(to: str, name: str, token: str, locale: str) -> EmailMessage:
    link = _link("/reset-password", token)
    minutes = get_settings().password_reset_ttl_minutes
    if locale == "en":
        subject = "Reset your password"
        text = (
            f"Hello {name},\n\nUse this link to choose a new password:\n{link}\n\n"
            f"The link expires in {minutes} minutes and can be used once. "
            "If you did not ask for this, you can ignore this message."
        )
    else:
        subject = "إعادة تعيين كلمة المرور"
        text = (
            f"مرحباً {name}،\n\nاستخدم الرابط التالي لاختيار كلمة مرور جديدة:\n{link}\n\n"
            f"ينتهي الرابط خلال {minutes} دقيقة ويُستخدم مرة واحدة فقط. "
            "إذا لم تطلب ذلك، تجاهل هذه الرسالة."
        )
    return EmailMessage(to=to, subject=subject, text=text, tags=("password_reset",))
