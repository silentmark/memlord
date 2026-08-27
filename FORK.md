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
| `ci: build from the default branch and tag images with the full local version` | Keeps the container build working in a fork: the image job triggers on the default branch instead of a hardcoded `main`, PyPI publishing is left to the canonical repository, and the build is amd64-only. It also publishes `X.Y.Z-custom.N` instead of truncated semver tags — `{{version}}`/`{{major}}.{{minor}}` dropped the local part, so a fork build claimed the upstream numbering and every later build of the same base version overwrote it. |
| `docs: fork notes` | This file. |

The first three are written to be upstreamable as they are; opening that PR is a
separate decision and has not been taken. Everything below them is ours to keep.

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

The `+` matters: the version comes from the git tag via `hatch-vcs`, and only a
PEP 440 local version survives that. A tag like `v0.3.1-custom.1` fails the build
outright. Container tags cannot contain `+`, so the published image ends up as
`X.Y.Z-custom.N`.

Files this stack touches — a conflict here means the rebase needs attention:
`src/memlord/config.py`, `src/memlord/embeddings.py`, `src/memlord/models/memory.py`,
`src/memlord/search.py`, `src/memlord/dao/memory.py`, `docker-entrypoint.sh`,
`.github/workflows/ci.yml`.
