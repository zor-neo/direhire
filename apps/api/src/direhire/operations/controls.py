from sqlalchemy.orm import Session

from direhire.errors import AppError
from direhire.models import PlatformControl


class PlatformControlService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enabled(self, key: str) -> bool:
        control = self.session.get(PlatformControl, key)
        return control is None or control.enabled

    def require(self, key: str, message: str) -> None:
        if not self.enabled(key):
            raise AppError(f"{key}_DISABLED", message, 503, retryable=True)
