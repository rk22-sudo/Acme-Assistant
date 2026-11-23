import json
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,  # the venv's python
        args=["-m", "app.mcp_server"],
        cwd=str(ROOT),
    )
    with anyio.fail_after(30):  # fail instead of hanging if the server won't start
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print("Tools exposed by the server:")
                for t in tools.tools:
                    print(f"  {t.name} - {(t.description or '').splitlines()[0]}")

                leave = next(t for t in tools.tools if t.name == "request_leave")
                print("\nInput schema Gemini will see for request_leave:")
                print(json.dumps(leave.input_schema, indent=2))

                result = await session.call_tool("get_leave_balance", {"employee_id": "E001"})
                print("\nget_leave_balance(E001) -> is_error:", result.is_error)
                print(json.dumps(result.structured_content, indent=2))


anyio.run(main)