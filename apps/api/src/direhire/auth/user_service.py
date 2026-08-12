from sqlalchemy import select
from sqlalchemy.orm import Session

from direhire.auth.oauth import CognitoIdentity
from direhire.models import User


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_or_create_from_cognito(self, identity: CognitoIdentity) -> User:
        statement = select(User).where(User.cognito_subject == identity.subject)
        user = self.session.scalar(statement)
        if user is None:
            user = User(cognito_subject=identity.subject, email=identity.email)
            self.session.add(user)
        elif user.email != identity.email:
            user.email = identity.email
        self.session.flush()
        return user
