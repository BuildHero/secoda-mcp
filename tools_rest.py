"""New read-only tools that call the Secoda REST API directly."""

import typing

from fastmcp import FastMCP

from client import SecodaClient, safe_json_call, validate_id


def register_rest_tools(mcp: FastMCP, client: SecodaClient) -> None:
    """Register new direct REST API tools on the MCP server."""

    # ---- Collections ----

    @mcp.tool()
    def list_collections(title: typing.Optional[str] = None, page: int = 1) -> str:
        """List all collections in the workspace. Optionally filter by title (substring match)."""
        params: dict = {}
        if title:
            params["title"] = title
        return safe_json_call(client.get_paginated, "collection/collections", params=params, page=page)

    @mcp.tool()
    def get_collection(collection_id: str) -> str:
        """Get a specific collection by ID, including its description and linked resources."""

        def _fetch() -> dict:
            validate_id(collection_id)
            return client.get(f"collection/collections/{collection_id}")

        return safe_json_call(_fetch)

    # ---- Documents ----

    @mcp.tool()
    def list_documents(title: typing.Optional[str] = None, page: int = 1) -> str:
        """List documents in the workspace. Optionally filter by title."""
        params: dict = {}
        if title:
            params["title"] = title
        return safe_json_call(
            client.get_paginated, "document/documents", params=params, page=page
        )

    @mcp.tool()
    def get_document(document_id: str) -> str:
        """Get a specific document by ID, including its full markdown content."""

        def _fetch() -> dict:
            validate_id(document_id)
            return client.get(f"document/documents/{document_id}")

        return safe_json_call(_fetch)

    # ---- Integrations ----

    @mcp.tool()
    def list_integrations(page: int = 1) -> str:
        """List all integrations (data sources) in the workspace. Returns integration IDs, names, and types."""
        return safe_json_call(client.get_paginated, "integration/integrations", page=page)

    # ---- Tables ----

    @mcp.tool()
    def list_tables(
        integration_id: typing.Optional[str] = None,
        title: typing.Optional[str] = None,
        page: int = 1,
    ) -> str:
        """List tables, optionally filtered by integration_id or title."""

        def _fetch() -> dict:
            params: dict = {}
            if integration_id:
                validate_id(integration_id)
                params["integration_id"] = integration_id
            if title:
                params["title"] = title
            return client.get_paginated("table/tables", params=params, page=page)

        return safe_json_call(_fetch)

    # ---- Questions ----

    @mcp.tool()
    def list_questions(page: int = 1) -> str:
        """List all Q&A questions in the workspace."""
        return safe_json_call(client.get_paginated, "question/questions", page=page)

    @mcp.tool()
    def get_question(question_id: str) -> str:
        """Get a specific question and its replies/answers by ID."""

        def _fetch() -> dict:
            validate_id(question_id)
            question = client.get(f"question/questions/{question_id}")
            try:
                replies = client.get_paginated(
                    "question/replies", params={"question": question_id}
                )
                question["replies"] = replies.get("results", [])
            except Exception:
                question["replies"] = []
                question["replies_error"] = "Failed to fetch replies"
            return question

        return safe_json_call(_fetch)

    # ---- Tags ----

    @mcp.tool()
    def list_tags(page: int = 1) -> str:
        """List all tags defined in the workspace."""
        return safe_json_call(client.get_paginated, "tag/tags", page=page)

    # ---- Custom Properties ----

    @mcp.tool()
    def list_custom_properties(page: int = 1) -> str:
        """List all custom property definitions in the workspace."""
        return safe_json_call(client.get_paginated, "resource/all_v2/custom_properties", page=page)
