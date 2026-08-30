"""enforce content uniqueness through a digest, not through the text column

Revision ID: e4a7c9b18d52
Revises: b7d1f0c25a3e
Create Date: 2026-08-30 09:00:00.000000

A unique index directly on `content` caps how long a memory may be: a btree
index row cannot exceed 1/3 of a buffer page, so Postgres refuses the write
with

    index row size 3480 exceeds btree version 4 maximum 2704
    for index "uq_memories_content_workspace"

That is an error, not a warning — anything past roughly 2.7 kB simply cannot be
stored. Moving the constraint onto `md5(content)` keeps the guarantee (one copy
of a given text per workspace) and removes the ceiling, because every digest is
32 bytes regardless of what it summarises.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4a7c9b18d52"
down_revision: Union[str, Sequence[str], None] = "b7d1f0c25a3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT = "uq_memories_content_workspace"

# Longest content a btree index row on (content, workspace_id) can still hold.
# Used only to explain a failed downgrade, never to reject a write.
BTREE_LIMIT = 2704


def upgrade() -> None:
    # A stored generated column, so the digest cannot drift from the text it
    # summarises — there is no code path that writes one without the other.
    op.add_column(
        "memories",
        sa.Column(
            "content_md5",
            sa.Text(),
            sa.Computed("md5(content)", persisted=True),
            nullable=False,
        ),
    )
    # Drop before create: the name is reused, and the old index is exactly the
    # thing being replaced.
    op.drop_constraint(CONSTRAINT, "memories", type_="unique")
    op.create_unique_constraint(CONSTRAINT, "memories", ["content_md5", "workspace_id"])


def downgrade() -> None:
    """Put the ceiling back — and refuse if anything already exceeds it.

    Rows longer than the btree limit are precisely what this migration made
    possible, so a blind downgrade would fail halfway through creating the
    index, leaving the table without any uniqueness guarantee at all. Check
    first and say what is in the way.
    """
    oversized = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM memories WHERE octet_length(content) > :limit"
        ),
        {"limit": BTREE_LIMIT},
    )
    if oversized:
        raise RuntimeError(
            f"{oversized} memory row(s) are longer than {BTREE_LIMIT} bytes and would "
            f"not fit a unique btree index on `content`. Shorten or delete them before "
            f"downgrading past {revision}."
        )

    op.drop_constraint(CONSTRAINT, "memories", type_="unique")
    op.create_unique_constraint(CONSTRAINT, "memories", ["content", "workspace_id"])
    op.drop_column("memories", "content_md5")
