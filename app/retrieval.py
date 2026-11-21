import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.embeddings import embed_texts

INDEX = Path(__file__).resolve().parent.parent / "data" / "index"


@lru_cache(maxsize=1)
def _load():
    chunks = json.loads((INDEX / "chunks.json").read_text(encoding="utf-8"))
    vectors = np.load(INDEX / "vectors.npy")
    return chunks, vectors


def search(query: str, k: int = 5) -> list[dict]:
    """Return the k most similar chunks, best first, each with a 'score'."""
    chunks, vectors = _load()
    q = embed_texts([query], "RETRIEVAL_QUERY")[0]
    scores = vectors @ q  # unit vectors, so this is cosine similarity
    top = np.argsort(scores)[::-1][:k]
    return [{**chunks[i], "score": float(scores[i])} for i in top]