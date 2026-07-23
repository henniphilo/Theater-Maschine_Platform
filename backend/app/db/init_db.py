from app.db.session import Base, engine
from app.models import asset  # noqa: F401 — Asset table (also Alembic 20260723_0002)
from app.models import cue  # noqa: F401 — Cue table (also Alembic 20260723_0004)
from app.models import device  # noqa: F401 — Device table (also Alembic 20260723_0005)
from app.models import entities  # noqa: F401
from app.models import production  # noqa: F401 — Production table (also Alembic 20260723_0001)
from app.models import rule  # noqa: F401 — Rule table (also Alembic 20260723_0006)
from app.models import tag  # noqa: F401 — Tag + asset_tags (also Alembic 20260723_0003)


def init_db() -> None:
    """Ensure tables exist.

    Prefer ``alembic upgrade head`` for schema changes in deployed environments.
    ``create_all`` remains for local/native bootstrap compatibility.
    """
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
