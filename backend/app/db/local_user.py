from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import User

LOCAL_EMAIL = "local@local"


def get_or_create_local_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == LOCAL_EMAIL))
    if user is not None:
        return user
    user = User(email=LOCAL_EMAIL, password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
