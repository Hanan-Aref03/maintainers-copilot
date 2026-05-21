from sqlalchemy.orm import Session
from app.domain.models import AuditLog
from app.infra.redaction import redact_payload
import uuid

class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def log(self, actor_id: uuid.UUID, action: str, target: str, details: dict = None):
        log = AuditLog(
            actor_id=actor_id,
            action=action,
            target=target,
            details=redact_payload(details or {})
        )
        self.db.add(log)
        self.db.commit()
        return log
