from mcp.server.mcpserver import MCPServer

from app import tools

mcp = MCPServer("handbook-tools")

for fn in (
    tools.get_leave_balance,
    tools.request_leave,
    tools.create_ticket,
    tools.list_tickets,
    tools.send_slack_message,
):
    mcp.tool()(fn)

if __name__ == "__main__":
    mcp.run()  # stdio by default