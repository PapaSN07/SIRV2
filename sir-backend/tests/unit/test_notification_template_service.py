"""Tests unitaires — templates notifications."""

from app.schemas.notifications import NotificationEventType
from app.services import notification_template_service


def test_render_email_contains_event_marker() -> None:
    sujet, corps = notification_template_service.render_email(
        NotificationEventType.INTERRUPTION_VALIDEE,
        entity_type="interruption",
        entity_id=42,
    )
    assert "[interruption_validee]" in sujet
    assert "42" in corps
    assert "TODO(SENELEC)" in corps


def test_render_sms_truncates_long_content() -> None:
    long_extra = {"file_name": "x" * 200}
    content = notification_template_service.render_sms(
        NotificationEventType.RAPPORT_PRET,
        entity_type="rapport",
        entity_id=1,
        extra=long_extra,
    )
    assert len(content) <= 160
