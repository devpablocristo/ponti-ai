from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from adapters.outbound.security.api_keys import is_valid_service_key


@dataclass(frozen=True)
class AuthContext:
    api_key: str
    user_id: str
    project_id: str


def require_headers(
    x_service_key: str | None = Header(default=None, alias="X-SERVICE-KEY"),
    x_user_id: str | None = Header(default=None, alias="X-USER-ID"),
    x_project_id: str | None = Header(default=None, alias="X-PROJECT-ID"),
) -> AuthContext:
    if not x_service_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-SERVICE-KEY requerido")
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-USER-ID requerido")
    if not x_project_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-PROJECT-ID requerido")
    if not is_valid_service_key(x_service_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service key invalida")
    return AuthContext(api_key=x_service_key, user_id=x_user_id, project_id=x_project_id)
