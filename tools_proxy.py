"""Existing 6 proxy tools — forwarded to Secoda's MCP backend endpoint."""

import typing

from fastmcp import FastMCP

from client import SecodaClient


def register_proxy_tools(mcp: FastMCP, client: SecodaClient) -> None:
    """Register the original 6 proxy tools on the MCP server."""

    @mcp.tool()
    def run_sql(query: str, integration_id: typing.Optional[str] = None) -> str:
        """Run a SQL query on the database."""
        return client.call_mcp_tool(
            "run_sql", {"query": query, "integration_id": integration_id}
        )

    @mcp.tool()
    def search_data_assets(query: str, page: int = 1) -> str:
        """Search for data assets in the database."""
        return client.call_mcp_tool(
            "search_data_assets", {"query": query, "page": page}
        )

    @mcp.tool()
    def search_documentation(query: str, page: int = 1) -> str:
        """Search for documentation in the database."""
        return client.call_mcp_tool(
            "search_documentation", {"query": query, "page": page}
        )

    @mcp.tool()
    def retrieve_entity(entity_id: str) -> str:
        """Retrieve an entity from the database."""
        return client.call_mcp_tool("retrieve_entity", {"entity_id": entity_id})

    @mcp.tool()
    def entity_lineage(entity_id: str) -> str:
        """Retrieve the lineage of an entity."""
        return client.call_mcp_tool("entity_lineage", {"entity_id": entity_id})

    @mcp.tool()
    def glossary() -> str:
        """Retrieve the glossary."""
        return client.call_mcp_tool("glossary", {})
