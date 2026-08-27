import asyncio
from functools import cache

import httpx
import numpy as np
from onnxruntime import InferenceSession
from tokenizers import Tokenizer

from memlord.config import settings


@cache
def _get_session() -> InferenceSession:
    return InferenceSession(str(settings.model_dir / "model.onnx"))


@cache
def _get_tokenizer() -> Tokenizer:
    # No truncation/padding: long inputs are chunked and padded manually in `embed`.
    return Tokenizer.from_file(str(settings.model_dir / "tokenizer.json"))


def _split_ids(ids: list[int], window: int = 510, stride: int = 384) -> list[list[int]]:
    if len(ids) <= window:
        return [ids]
    return [ids[i : i + window] for i in range(0, len(ids) - window + stride, stride)]


async def embed(text: str) -> list[float]:
    """Embed a single text with the configured provider."""
    if settings.embedding_provider == "http":
        return await _embed_http(text)
    return await _embed_onnx(text)


@cache
def _get_client() -> httpx.AsyncClient:
    headers = {}
    if settings.embedding_api_key:
        headers["Authorization"] = f"Bearer {settings.embedding_api_key}"
    return httpx.AsyncClient(timeout=settings.embedding_timeout, headers=headers)


async def _embed_http(text: str) -> list[float]:
    """Embed via an OpenAI-compatible /v1/embeddings endpoint.

    Chunking is the server's business here: it owns the tokenizer and the context
    window, so splitting the text locally would only guess at both.
    """
    if not settings.embedding_url:
        raise RuntimeError("embedding_provider='http' requires embedding_url")

    response = await _get_client().post(
        settings.embedding_url,
        json={"input": text, "model": settings.embedding_model},
    )
    response.raise_for_status()
    vector = response.json()["data"][0]["embedding"]

    # A wrong dimension must fail loudly: the column would reject it anyway, and
    # a silent mismatch between provider and schema is hard to spot afterwards.
    if len(vector) != settings.embedding_dim:
        raise RuntimeError(
            f"embedding endpoint returned {len(vector)} dimensions, "
            f"expected {settings.embedding_dim}"
        )
    return vector


async def _embed_onnx(text: str) -> list[float]:
    tokenizer = _get_tokenizer()
    session = _get_session()

    # XLM-R special tokens (paraphrase-multilingual-MiniLM-L12-v2).
    cls_id = tokenizer.token_to_id("<s>")
    sep_id = tokenizer.token_to_id("</s>")
    pad_id = tokenizer.token_to_id("<pad>")
    if cls_id is None or sep_id is None or pad_id is None:
        raise RuntimeError("tokenizer missing expected special tokens (<s>/</s>/<pad>)")

    # Encode without special tokens, chunk on content, then wrap each chunk in
    # <s> ... </s> so every window matches the framing the model was trained on.
    encoding = tokenizer.encode(text, add_special_tokens=False)
    chunks = [[cls_id, *c, sep_id] for c in _split_ids(encoding.ids)]
    width = max(len(c) for c in chunks)

    input_ids = np.full((len(chunks), width), pad_id, dtype=np.int64)
    attention_mask = np.zeros((len(chunks), width), dtype=np.int64)
    for i, chunk in enumerate(chunks):
        input_ids[i, : len(chunk)] = chunk
        attention_mask[i, : len(chunk)] = 1
    token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

    loop = asyncio.get_running_loop()
    future: asyncio.Future[list[np.ndarray]] = loop.create_future()

    def _callback(results: list[np.ndarray], _user_data: None, err: str) -> None:
        if err:
            loop.call_soon_threadsafe(future.set_exception, RuntimeError(err))
        else:
            loop.call_soon_threadsafe(future.set_result, results)

    session.run_async(
        None,
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
        _callback,
        None,
    )

    outputs = await future

    # per-chunk mean pooling with attention mask
    token_embeddings = np.asarray(outputs[0])  # (n_chunks, seq_len, 384)
    mask = attention_mask[..., np.newaxis].astype(np.float32)  # (n_chunks, seq_len, 1)
    pooled = (token_embeddings * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1e-9)

    # L2 normalize each chunk, then average chunks and normalize again
    pooled /= np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
    mean = pooled.mean(axis=0)
    mean /= np.linalg.norm(mean).clip(min=1e-9)

    return mean.astype(np.float32).tolist()
