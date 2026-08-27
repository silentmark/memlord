"""merge the upstream TOTP head with the fork's embedding/digest head

Revision ID: a1f3c7d92b40
Revises: e4a7c9b18d52, d4e5f6a1b2c3
Create Date: 2026-09-22 00:00:00.000000

Rebase onto v0.3.2 put two revisions side by side rather than in a line. Both
declare the same parent `73136588cb14`:

    73136588cb14 ─┬─ d4e5f6a1b2c3   (upstream, totp_secret)
                  └─ b7d1f0c25a3e ─ e4a7c9b18d52   (fork, embedding dim + digest)

Alembic refuses to upgrade a tree with two heads, so the container would come
up and then fail on the entrypoint's `alembic upgrade head` with "Multiple head
revisions are present". This revision joins them and does nothing else.

⚠ The join is a merge, not a re-parenting of the fork chain onto the upstream
one, and that is deliberate. The deployed database has `e4a7c9b18d52` stamped
and has never seen `d4e5f6a1b2c3`. Hanging the fork chain below the TOTP
revision would tell Alembic that TOTP is already applied — it walks down from
the stamped revision — and `totp_secret` would silently never be created.
Through the merge the upgrade path from `e4a7c9b18d52` still runs the TOTP
revision, which is what the column actually needs.

The same collision returns whenever upstream adds a migration on a base we have
also built on. The answer is another merge revision, never an edit to an
upstream file: editing one conflicts on every later rebase and rewrites history
that other clones may already have applied.

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "a1f3c7d92b40"
down_revision: Union[str, Sequence[str], None] = ("e4a7c9b18d52", "d4e5f6a1b2c3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Nothing to do: a merge revision only joins two branches of history."""


def downgrade() -> None:
    """Nothing to do: splitting the branches back apart needs no DDL."""
