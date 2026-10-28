"""Keep the legacy local-runtime revision addressable.

The Docker demo volume was created by an earlier branch whose latest
revision was ``f8b4d1e7c903``.  The current application no longer needs
that branch's schema changes, but Alembic must still be able to resolve the
revision before applying the current migrations.  This intentionally no-op
revision preserves upgrade compatibility for existing demo volumes.
"""

from collections.abc import Sequence

revision: str = "f8b4d1e7c903"
down_revision: str | Sequence[str] | None = "d2a1d3f4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
