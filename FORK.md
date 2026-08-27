# Fork notes

The `custom` branch carries a small stack of patches on top of upstream
`MyrikLD/memlord`. `main` is kept as a plain mirror of upstream, so the stack can
always be rebased onto a fresh release.

## The stack

| commit | what it changes |
| --- | --- |
| `feat(config): configurable embedding dimension` | `settings.embedding_dim` replaces the hardcoded `Vector(384)` in the ORM model, the hybrid-search bind parameter and the DAO. Default is unchanged. |
| `feat(embeddings): optional OpenAI-compatible HTTP provider` | `settings.embedding_provider` selects between the bundled ONNX model (default, untouched) and a remote `/v1/embeddings` endpoint. The entrypoint skips the model download when the remote provider is in use. |
| `feat(migrations): resize embedding column to configured dimension` | One revision on top of the upstream head. Rewrites `memories.embedding` when the configured dimension differs from what the database has, and rebuilds the HNSW index around it. A no-op at the default 384, so `alembic-autogen-check` stays green. |
| `fix(models): enforce content uniqueness through a digest` | A unique index on `content` itself caps every memory at roughly 2.7 kB — a btree index row cannot exceed 1/3 of a buffer page, so longer writes are refused outright with `index row size N exceeds btree version 4 maximum 2704`. The constraint moves onto a stored generated `content_md5`, which keeps the guarantee and drops the ceiling. One revision on top of the dimension one; the DAO's content lookups compare the digest first so they still ride an index. |
| `ci: build from the default branch and tag images with the full local version` | Keeps the container build working in a fork: the image job triggers on the default branch instead of a hardcoded `main`, PyPI publishing is left to the canonical repository, and the build is amd64-only. It also publishes `X.Y.Z-custom.N` instead of truncated semver tags — `{{version}}`/`{{major}}.{{minor}}` dropped the local part, so a fork build claimed the upstream numbering and every later build of the same base version overwrote it. |
| `docs: fork notes` | This file, plus the Alembic merge revision that joins our chain with the upstream one. |

The three `feat:` commits and the `fix:` commit are written to be upstreamable as
they are; opening that PR is a separate decision and has not been taken. The `ci:`
and `docs:` commits are ours to keep.

The CI work sits last on purpose, so workflow conflicts stay in one place. It was
two commits until 2026-08-29 and is now one — same for the docs, which were also
two. Keep it that way: one commit per concern, so the stack stays readable after
a year of rebases.

⚠ Squashing rewrites the tip, which invalidates the `org.opencontainers.image.revision`
label on any already-published image. Tag and rebuild after every history rewrite,
otherwise the drift report compares against a commit that no longer exists on the
branch and reports nonsense.

## Using the HTTP provider

```
MEMLORD_EMBEDDING_PROVIDER=http
MEMLORD_EMBEDDING_URL=http://localhost:8080/v1/embeddings
MEMLORD_EMBEDDING_MODEL=default
MEMLORD_EMBEDDING_DIM=1024
```

`MEMLORD_EMBEDDING_DIM` must match what the endpoint returns; a mismatch raises at
embed time rather than being written to the column. Switching dimensions on an
existing database drops the stored vectors — run once with `REEMBED=1` afterwards.

## Rebasing onto a new upstream release

```sh
git fetch upstream --tags
git switch main && git merge --ff-only upstream/main && git push
git switch custom
git rebase --onto vX.Y.Z <previous-tag> custom
```

Then tag as `vX.Y.Z+custom.N` and let CI publish the image.

### When upstream adds a migration

Check the head count before tagging. Our revisions hang off whatever the upstream
head was when they were written, so an upstream migration written against the same
parent lands beside ours rather than above them, and Alembic refuses a tree with
two heads. The container starts and then dies on the entrypoint's
`alembic upgrade head`.

Measured on v0.3.2: upstream's `d4e5f6a1b2c3` (totp_secret) and our
`b7d1f0c25a3e` both declared `73136588cb14` as parent.

Join them with a merge revision whose `down_revision` is the tuple of both heads,
and put it in the `docs:` commit. Two things not to do instead:

- do not re-parent our chain under the upstream revision. The deployed database
  has our head stamped and has never run the upstream one, and Alembic decides
  what to apply by walking down from the stamped revision — so the upstream
  migration would be treated as done and its column would never be created;
- do not edit the upstream migration file. It conflicts on every later rebase and
  rewrites history that other clones may already have applied.

The `+` matters: the version comes from the git tag via `hatch-vcs`, and only a
PEP 440 local version survives that. A tag like `v0.3.1-custom.1` fails the build
outright. Container tags cannot contain `+`, so the published image ends up as
`X.Y.Z-custom.N`.

Files this stack touches — a conflict here means the rebase needs attention:
`src/memlord/config.py`, `src/memlord/embeddings.py`, `src/memlord/models/memory.py`,
`src/memlord/search.py`, `src/memlord/dao/memory.py`, `docker-entrypoint.sh`,
`.github/workflows/ci.yml`.
