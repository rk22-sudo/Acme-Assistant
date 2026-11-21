import os
import time

import numpy as np
from google.genai import types
from google.genai.errors import APIError

from app.llm import _get_client

EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
DIMS = 768  # smaller vectors = smaller index, quality is still fine for this corpus
MAX_ATTEMPTS = 6


def embed_texts(texts: list[str], task_type: str) -> np.ndarray:
    """task_type: 'RETRIEVAL_DOCUMENT' for chunks, 'RETRIEVAL_QUERY' for questions.
    Returns an (n, DIMS) float32 array of unit-length vectors."""
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = _get_client().models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=DIMS,
                ),
            )
            break
        except APIError as exc:
            if "PerDay" in str(exc):
                raise RuntimeError(
                    "Daily embedding quota used up. Progress is saved; rerun after the quota resets."
                ) from exc
            if exc.code not in (429, 500, 503) or attempt == MAX_ATTEMPTS - 1:
                raise
            wait = min(60, 5 * 2**attempt)
            print(f"  embed error {exc.code}, retrying in {wait}s...")
            time.sleep(wait)

    vecs = np.array([e.values for e in resp.embeddings], dtype=np.float32)
    # Shortened vectors aren't unit length, so normalize. Then dot product == cosine similarity.
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs