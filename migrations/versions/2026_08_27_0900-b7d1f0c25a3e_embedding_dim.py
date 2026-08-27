"""embedding dimension from settings

Revision ID: b7d1f0c25a3e
Revises: 73136588cb14
Create Date: 2026-08-27 09:00:00.000000

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from memlord.config import settings


# revision identifiers, used by Alembic.
revision: str = 'b7d1f0c25a3e'
down_revision: Union[str, Sequence[str], None] = '73136588cb14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_memories_embedding"
DEFAULT_DIM = 384


def upgrade() -> None:
    """Widen (or narrow) the embedding column to the configured dimension."""
    _resize(settings.embedding_dim)


def downgrade() -> None:
    """Restore the built-in model's dimension."""
    _resize(DEFAULT_DIM)


def _resize(dim: int) -> None:
    # No-op on the default dimension, which keeps this migration invisible to
    # anyone running the bundled model — and keeps model and migrations in sync
    # for autogenerate checks.
    if _column_dim() == dim:
        return

    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
    # Vectors cannot be cast to another width, so existing ones are dropped.
    # Rebuild them with REEMBED=1 after the upgrade.
    op.execute("UPDATE memories SET embedding = NULL")
    op.execute(f"ALTER TABLE memories ALTER COLUMN embedding TYPE vector({dim})")
    op.create_index(
        INDEX_NAME,
        "memories",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def _column_dim() -> int | None:
    """Dimension the database currently has, or None if it cannot be read."""
    declared = op.get_bind().scalar(
        sa.text(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = to_regclass('memories') "
            "AND attname = 'embedding' AND NOT attisdropped"
        )
    )
    match = re.search(r"\((\d+)\)", declared or "")
    return int(match.group(1)) if match else None
