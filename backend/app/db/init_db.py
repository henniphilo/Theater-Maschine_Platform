from app.db.session import Base, engine
from app.models import entities  # noqa: F401
from app.models import production  # noqa: F401 — Production table (also Alembic 20260723_0001)


def init_db() -> None:
    """Ensure tables exist.

    Prefer ``alembic upgrade head`` for schema changes in deployed environments.
    ``create_all`` remains for local/native bootstrap compatibility.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
