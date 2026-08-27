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
| `ci: build from the default branch, skip PyPI outside the canonical repo` | Keeps the container build working in a fork. Deliberately last in the stack, so workflow conflicts stay in one place. |

The first three are written to be upstreamable as they are.

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
