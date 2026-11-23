import json
import sys

import anyio

from app.agent import run


async def main() -> None:
    question = " ".join(sys.argv[1:]) or "How many annual leave days do I have left?"
    result = await run([{"role": "user", "content": question}], employee_id="E001")
    print("REPLY:", result["reply"])
    print("\nTOOL CALLS:", json.dumps(result["tool_calls"], indent=2)[:2000])
    print("\nSOURCES:", [(s["n"], s["title"]) for s in result["sources"]])


anyio.run(main)