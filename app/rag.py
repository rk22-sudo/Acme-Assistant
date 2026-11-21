import re

from app.llm import chat
from app.prompts import RAG_RULES, SYSTEM_PROMPT
from app.retrieval import search

TOP_K = 5


def _search_query(messages: list[dict]) -> str:
    # Follow-ups like "what about contractors?" need the previous question too.
    user_turns = [m["content"] for m in messages if m["role"] == "user"]
    return " ".join(user_turns[-2:])


def answer(messages: list[dict]) -> dict:
    hits = search(_search_query(messages), k=TOP_K)
    context = "\n\n".join(
        f"[{i}] {h['title']} > {h['heading']}\n{h['text']}" for i, h in enumerate(hits, 1)
    )
    system = f"{SYSTEM_PROMPT}\n{RAG_RULES}\nSources:\n\n{context}"
    reply = chat(messages, system)

    # Only report sources the model actually cited, so refusals show none.
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", reply)}
    sources = [
        {"n": i, "title": h["title"], "heading": h["heading"], "url": h["url"], "score": round(h["score"], 3)}
        for i, h in enumerate(hits, 1)
        if i in cited
    ]
    return {"reply": reply, "sources": sources}