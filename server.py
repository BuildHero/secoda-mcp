"""Secoda MCP Server — enhanced fork with direct REST API tools."""

import os

from fastmcp import FastMCP

from client import SecodaClient
from prompt import MCP_PROMPT
from tools_proxy import register_proxy_tools
from tools_rest import register_rest_tools

# --------------------------------
# Configuration
# --------------------------------

API_URL = os.getenv("API_URL", "https://app.secoda.co/api/v1/")
API_TOKEN = os.getenv("API_TOKEN")

if not API_TOKEN:
    raise ValueError("API_TOKEN environment variable is required")

# --------------------------------
# Server
# --------------------------------

client = SecodaClient(API_URL, API_TOKEN)

mcp = FastMCP(
    name="Secoda MCP",
    instructions=MCP_PROMPT,
)

register_proxy_tools(mcp, client)
register_rest_tools(mcp, client)

if __name__ == "__main__":
    mcp.run()
