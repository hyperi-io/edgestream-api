from typing import Any, Dict, Optional
from fastapi import Request, BackgroundTasks
from sqlalchemy.orm import sessionmaker

from edgestream.models.system.audit import AuditEvent
from edgestream.core.config import Logger

SENSITIVE_KEYS = {
    "password", "token", "access_token", "secret", "otp",
    "authorization", "private_key", "certificate", "api_key"
}


def redact_sensitive_info(data: Any) -> Any:
    """
    Recursively scans and redacts sensitive keys from nested audit details.
    Ensures that credentials used in Source/Destination setups aren't logged.
    """
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if str(k).lower() in SENSITIVE_KEYS else redact_sensitive_info(v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [redact_sensitive_info(i) for i in data]
    return data


def enqueue_audit(
        background: BackgroundTasks,
        session_factory: sessionmaker,
        request: Request,
        *,
        event_type: str,
        result: str,
        actor_id: Optional[str] = None,
        actor_type: Optional[str] = "user",
        subject_id: Optional[str] = None,
        subject_type: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
):
    """
    Asynchronously logs a security or system event to the audit table.

    Extracts HTTP context (IP, UA, Method) immediately while the request
    is alive to prevent race conditions in the background thread.
    """
    client_ip = request.client.host if request.client else "0.0.0.0"
    user_agent = request.headers.get("User-Agent")
    route_path = request.url.path
    http_method = request.method

    request_id = (
            getattr(request.state, "correlation_id", None) or
            getattr(request.state, "request_id", None)
    )

    safe_details = redact_sensitive_info(details) if details else None

    def audit_task_execution():
        with session_factory() as db:
            try:
                event = AuditEvent(
                    event_type=event_type,
                    result=result,
                    actor_id=actor_id,
                    actor_type=actor_type,
                    subject_id=subject_id,
                    subject_type=subject_type,
                    request_id=str(request_id) if request_id else None,
                    ip=client_ip,
                    user_agent=user_agent,
                    route=route_path,
                    method=http_method,
                    status_code=status_code,
                    reason=reason,
                    details=safe_details,
                )
                db.add(event)
                db.commit()
            except Exception as e:
                db.rollback()
                Logger.logger.error(
                    f"CRITICAL AUDIT FAILURE: Could not persist event '{event_type}'. "
                    f"Error: {e}. Payload: {safe_details}"
                )

    background.add_task(audit_task_execution)
