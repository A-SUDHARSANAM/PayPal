"""Authentication boundary for user-facing FastAPI endpoints."""
from dataclasses import dataclass
from functools import lru_cache
import httpx
import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import settings

bearer = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class CurrentUser:
    id: str

@lru_cache(maxsize=1)
def jwks_url() -> str:
    if not settings.supabase_jwt_issuer:
        raise RuntimeError("SUPABASE_JWT_ISSUER must be configured")
    return f"{settings.supabase_jwt_issuer.rstrip('/')}/.well-known/jwks.json"

async def current_user(credentials: HTTPAuthorizationCredentials | None = Security(bearer)) -> CurrentUser:
    if not credentials:
        raise HTTPException(401, "Missing bearer token")
    if not settings.supabase_jwt_issuer:
        raise HTTPException(503, "Authentication is not configured")
    try:
        header = jwt.get_unverified_header(credentials.credentials)
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(jwks_url())
            response.raise_for_status()
            keys = response.json().get("keys", [])
        match = next((candidate for candidate in keys if candidate.get("kid") == header.get("kid")), None)
        if not match: raise ValueError("No matching signing key")
        key = jwt.PyJWK.from_dict(match).key
        claims = jwt.decode(credentials.credentials, key, algorithms=["ES256", "RS256"], audience=settings.supabase_jwt_audience, issuer=settings.supabase_jwt_issuer)
        subject = claims.get("sub")
        if not isinstance(subject, str): raise ValueError("Token has no subject")
        return CurrentUser(id=subject)
    except Exception as exc:
        raise HTTPException(401, "Invalid bearer token") from exc
