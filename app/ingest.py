import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from collections import Counter
import numpy as np

from app.embeddings import embed_texts

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "data" / "handbook"
INDEX = ROOT / "data" / "index"
CACHE = INDEX / "embed_cache.jsonl"

MAX_CHARS = 1500
MIN_CHARS = 80
BATCH = 32
BASE_URL = "https://handbook.gitlab.com/handbook/"

FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
TITLE = re.compile(r"^title:\s*(.+)$", re.M)
SHORTCODE = re.compile(r"\{\{[<%].*?[>%]\}\}", re.S)
HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")


def parse_file(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    title = path.stem
    m = FRONT.match(raw)
    if m:
        t = TITLE.search(m.group(1))
        if t:
            title = t.group(1).strip().strip("\"'")
        raw = raw[m.end():]
    return title, SHORTCODE.sub("", raw)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return [(heading_path, body)] split on markdown headings."""
    sections, stack, buf, in_code = [], [], [], False

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append((" > ".join(h for _, h in stack), body))
        buf.clear()

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2)))
        else:
            buf.append(line)
    flush()
    return sections


def pack(body: str) -> list[str]:
    """Pack paragraphs into pieces of at most MAX_CHARS."""
    pieces, cur = [], ""
    for para in body.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        while len(para) > MAX_CHARS:  # e.g. giant tables
            if cur:
                pieces.append(cur)
                cur = ""
            pieces.append(para[:MAX_CHARS])
            para = para[MAX_CHARS:]
        if cur and len(cur) + len(para) + 2 > MAX_CHARS:
            pieces.append(cur)
            cur = ""
        cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        pieces.append(cur)
    return pieces


def page_url(path: Path) -> str:
    parts = list(path.relative_to(DOCS).with_suffix("").parts)
    if parts[-1] == "_index":
        parts.pop()
    return BASE_URL + "/".join(parts) + "/"


def build_chunks() -> list[dict]:
    chunks, seen = [], set()
    for path in sorted(DOCS.rglob("*.md")):
        title, text = parse_file(path)
        url = page_url(path)
        for heading, body in split_sections(text):
            for piece in pack(body):
                if len(piece) < MIN_CHARS:
                    continue
                embed_input = f"{title} | {heading}\n{piece}" if heading else f"{title}\n{piece}"
                cid = hashlib.sha1(embed_input.encode("utf-8")).hexdigest()[:16]
                if cid in seen:
                    continue
                seen.add(cid)
                chunks.append({
                    "id": cid,
                    "source": path.relative_to(DOCS).as_posix(),
                    "url": url,
                    "title": title,
                    "heading": heading,
                    "text": piece,
                    "embed_input": embed_input,
                })
    return chunks


def load_cache() -> dict[str, list[float]]:
    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                cache[row["id"]] = row["v"]
            except (json.JSONDecodeError, KeyError):
                pass  # a half-written last line from an interrupted run
    return cache


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="count chunks, no API calls")
    parser.add_argument("--only", nargs="+", help="only include these top-level folders")
    args = parser.parse_args()

    chunks = build_chunks()
    if args.only:
        chunks = [c for c in chunks if c["source"].split("/")[0] in args.only]
    total_chars = sum(len(c["text"]) for c in chunks)
    print(f"{len(chunks)} chunks, {total_chars:,} characters, avg {total_chars // max(len(chunks), 1)} per chunk")
    for folder, n in Counter(c["source"].split("/")[0] for c in chunks).most_common():
        print(f"  {folder}: {n}")
    if args.dry_run:
        return

    INDEX.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    todo = [c for c in chunks if c["id"] not in cache]
    print(f"{len(cache)} already embedded, {len(todo)} to do")

    with CACHE.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            try:
                vecs = embed_texts([c["embed_input"] for c in batch], "RETRIEVAL_DOCUMENT")
            except RuntimeError as exc:
                print(exc)
                return
            for c, v in zip(batch, vecs):
                cache[c["id"]] = [round(float(x), 5) for x in v]
                f.write(json.dumps({"id": c["id"], "v": cache[c["id"]]}) + "\n")
            f.flush()
            print(f"  embedded {min(i + BATCH, len(todo))}/{len(todo)}")
            time.sleep(1)

    vectors = np.array([cache[c["id"]] for c in chunks], dtype=np.float32)
    np.save(INDEX / "vectors.npy", vectors)
    for c in chunks:
        del c["embed_input"]
    (INDEX / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    print(f"Saved index: {vectors.shape[0]} chunks x {vectors.shape[1]} dims")

if __name__ == "__main__":
    main()
