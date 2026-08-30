"""A memory longer than a btree index row must still be storable.

Uniqueness of `content` used to be a unique index on the text column itself,
which capped every memory at roughly 2.7 kB: past that, Postgres refused the
write with `index row size N exceeds btree version 4 maximum 2704`. The
constraint now sits on `md5(content)`, so length no longer decides whether a
memory can be saved. These tests pin both halves of that: long content goes in,
and uniqueness still holds.
"""

import hashlib

import pytest
import sqlalchemy as sa

from memlord.dao import MemoryDao
from memlord.models import Memory
from memlord.schemas import MemoryType


def _incompressible(n_bytes: int) -> str:
    """Text that cannot be squeezed under the limit we are testing against.

    ⚠ A repeated phrase is useless here: Postgres compresses the value inside
    the index tuple, so `"some sentence " * 400` slips below 2704 bytes and the
    insert succeeds even on the old schema — the test passes while proving
    nothing. A chain of sha256 digests has no redundancy to remove.
    """
    chunks: list[str] = []
    digest = b"memlord"
    while sum(len(c) for c in chunks) < n_bytes:
        digest = hashlib.sha256(digest).digest()
        chunks.append(digest.hex())
    return "".join(chunks)[:n_bytes]


# Comfortably past the old ceiling of 2704 *bytes*, which is what the index
# measured — not characters.
LONG = _incompressible(4096)


async def test_long_content_is_storable(session, user_id, workspace_id):
    assert len(LONG.encode()) > 2704

    dao = MemoryDao(session, user_id)
    mid, created = await dao.create(
        content=LONG,
        memory_type=MemoryType.fact,
        metadata={},
        tags=set(),
        name="long content",
        workspace_id=workspace_id,
    )

    assert created is True
    stored = await session.scalar(sa.select(Memory.content).where(Memory.id == mid))
    assert stored == LONG


async def test_long_content_stays_idempotent(session, user_id, workspace_id):
    """The digest must not weaken the guarantee it replaced."""
    dao = MemoryDao(session, user_id)
    first, created = await dao.create(
        content=LONG,
        memory_type=MemoryType.fact,
        metadata={},
        tags=set(),
        name="long content",
        workspace_id=workspace_id,
    )
    assert created is True

    second, created_again = await dao.create(
        content=LONG,
        memory_type=MemoryType.fact,
        metadata={},
        tags=set(),
        name="long content, second attempt",
        workspace_id=workspace_id,
    )

    assert created_again is False
    assert second == first


async def test_duplicate_content_is_still_rejected_at_the_database(
    session, user_id, workspace_id
):
    """The constraint, not just the DAO's pre-check, has to hold the line."""
    dao = MemoryDao(session, user_id)
    await dao.create(
        content=LONG,
        memory_type=MemoryType.fact,
        metadata={},
        tags=set(),
        name="long content",
        workspace_id=workspace_id,
    )
    await session.flush()

    # Bypass the DAO entirely — this is the write the unique index must refuse.
    with pytest.raises(sa.exc.IntegrityError):
        await session.execute(
            sa.insert(Memory).values(
                content=LONG,
                memory_type=MemoryType.fact,
                extra_data={},
                created_by=user_id,
                workspace_id=workspace_id,
                name="a different name, the same content",
            )
        )
