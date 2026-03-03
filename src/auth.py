"""Multi-tenant Azure Entra ID authentication (with dev JWT fallback)."""
from typing import Optional
import structlog
from fastapi import HTTPException, Header
from jose import jwt, JWTError
from src.models import TenantUserContext
from src.config import get_settings

logger = structlog.get_logger(__name__)

MOCK_USERS = {
    "user-t1-001": TenantUserContext(user_id="user-t1-001", tenant_id="tenant-contoso", name="Alice Johnson", email="alice@contoso.com", roles=["employee"], department="Engineering"),
    "user-t1-002": TenantUserContext(user_id="user-t1-002", tenant_id="tenant-contoso", name="Bob Smith", email="bob@contoso.com", roles=["manager"], department="Finance"),
    "user-t2-001": TenantUserContext(user_id="user-t2-001", tenant_id="tenant-fabrikam", name="Carol Lee", email="carol@fabrikam.com", roles=["employee"], department="HR"),
}


def create_test_token(user_id: str) -> str:
    settings = get_settings()
    user = MOCK_USERS.get(user_id)
    payload = {"sub": user_id, "tid": user.tenant_id if user else "tenant-contoso"}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def get_current_user(authorization: Optional[str] = Header(None)) -> TenantUserContext:
    """Validate JWT and extract multi-tenant user context."""
    settings = get_settings()
    if not authorization:
        logger.warning("no_auth_header_dev_fallback")
        return MOCK_USERS["user-t1-001"]
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        user = MOCK_USERS.get(user_id)
        if not user:
            tenant_id = payload.get("tid", "unknown")
            user = TenantUserContext(
                user_id=user_id, tenant_id=tenant_id,
                name=payload.get("name", "Unknown User"),
                email=payload.get("email", f"{user_id}@unknown.com"),
                roles=payload.get("roles", ["employee"]),
                department=payload.get("department", "General"),
            )
        logger.info("user_authenticated", user_id=user.user_id, tenant_id=user.tenant_id)
        return user
    except JWTError as exc:
        logger.error("jwt_error", error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid token")
