"""Service — templates notifications email/SMS (Sprint 8)."""

from app.schemas.notifications import NotificationEventType

# TODO(SENELEC): valider charte et contenus métier avec l'équipe SENELEC


def render_email(event_type: str, *, entity_type: str, entity_id: int, extra: dict | None = None) -> tuple[str, str]:
    extra = extra or {}
    marker = f"[{event_type}]"
    labels = {
        NotificationEventType.INTERRUPTION_CREEE: "Nouvelle interruption",
        NotificationEventType.INTERRUPTION_CLOTUREE: "Interruption clôturée",
        NotificationEventType.INTERRUPTION_VALIDEE: "Interruption validée",
        NotificationEventType.RAPPORT_PRET: "Rapport prêt",
        NotificationEventType.NAPT_SOUMIS: "NAPT soumis",
    }
    label = labels.get(event_type, "Notification SIR")
    sujet = f"{marker} {label} #{entity_id}"
    corps = (
        f"<html><body><h1>{label}</h1>"
        f"<p>Type entité : {entity_type}</p>"
        f"<p>Identifiant : {entity_id}</p>"
    )
    if event_type == NotificationEventType.RAPPORT_PRET:
        file_name = extra.get("file_name", "")
        task_id = extra.get("task_id", "")
        corps += f"<p>Fichier : {file_name}</p><p>Task : {task_id}</p>"
    corps += "<p><em># TODO(SENELEC) — template HTML à valider</em></p></body></html>"
    return sujet, corps


def render_sms(event_type: str, *, entity_type: str, entity_id: int, extra: dict | None = None) -> str:
    extra = extra or {}
    marker = f"[{event_type}]"
    base = f"{marker} SIR {entity_type} #{entity_id}"
    if event_type == NotificationEventType.RAPPORT_PRET:
        base = f"{marker} Rapport pret: {extra.get('file_name', entity_id)}"
    if len(base) > 160:
        return base[:157] + "..."
    return base
