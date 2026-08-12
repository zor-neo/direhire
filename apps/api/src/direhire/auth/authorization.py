from direhire.auth.dependencies import CurrentUser
from direhire.errors import AppError


def require_superadmin(user: CurrentUser) -> None:
    if user.role != "SUPERADMIN":
        raise AppError("AUTHORIZATION_DENIED", "You do not have permission to do that.", 403)
