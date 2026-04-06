"""Secoda REST API client with shared HTTP logic, pagination, and error handling."""

import json
import math
import re
import typing
from urllib.parse import quote

import requests

# Fields to strip from responses to reduce token usage
NOISY_FIELDS = {
    "bookmarked_by",
    "multiplayers",
    "multiplayer_last_modified_by",
    "multiplayer_last_modified",
    "search_metadata",
    "current_user_permissions",
    "workspace_id",
    "definition_version",
    "entity_chat_context",
    "stale",
    "stale_at",
    "force_merge_fields",
}

# UUID pattern for validating entity IDs
_UUID_RE = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")


def validate_id(entity_id: str) -> str:
    """Validate that an ID looks like a UUID. Prevents path traversal."""
    if not _UUID_RE.match(entity_id):
        raise ValueError(f"Invalid entity ID format: must be a UUID, got '{entity_id[:50]}'")
    return entity_id


def trim_response(obj: typing.Any, depth: int = 0) -> typing.Any:
    """Recursively strip noisy fields from API response objects."""
    if depth > 50:
        return obj
    if isinstance(obj, dict):
        return {
            k: trim_response(v, depth + 1) for k, v in obj.items() if k not in NOISY_FIELDS
        }
    if isinstance(obj, list):
        return [trim_response(item, depth + 1) for item in obj]
    return obj


def safe_json_call(func: typing.Callable, *args: typing.Any, **kwargs: typing.Any) -> str:
    """Execute a function, serialize result to JSON, and catch HTTP/connection errors."""
    try:
        result = func(*args, **kwargs)
        return json.dumps(result)
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        body = e.response.text[:500] if e.response is not None else ""
        return json.dumps({"error": f"HTTP {status}", "detail": body})
    except requests.exceptions.ConnectionError:
        return json.dumps(
            {"error": "Connection failed", "detail": "Secoda API unreachable"}
        )
    except requests.exceptions.Timeout:
        return json.dumps(
            {"error": "Timeout", "detail": "Request timed out after 30s"}
        )
    except ValueError as e:
        return json.dumps({"error": "Validation error", "detail": str(e)[:500]})
    except Exception:
        return json.dumps(
            {"error": "Unexpected error", "detail": "An internal error occurred"}
        )


class SecodaClient:
    """Read-only client for the Secoda REST API."""

    def __init__(self, api_url: str, api_token: str) -> None:
        self.api_url = api_url if api_url.endswith("/") else f"{api_url}/"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            }
        )
        self.session.timeout = 30

    # ---- Proxy method (for existing 6 tools) ----

    def call_mcp_tool(self, tool_name: str, args: dict) -> str:
        """Forward a tool call to Secoda's MCP backend endpoint."""
        return safe_json_call(self._call_mcp_tool_inner, tool_name, args)

    def _call_mcp_tool_inner(self, tool_name: str, args: dict) -> dict:
        response = self.session.post(
            f"{self.api_url}ai/mcp/tools/call/",
            json={"name": tool_name, "arguments": args},
        )
        response.raise_for_status()
        return response.json()

    # ---- Direct REST API methods (for new tools) ----

    def get(self, path: str, params: typing.Optional[dict] = None) -> dict:
        """GET a single REST API endpoint. Returns parsed JSON dict."""
        url = f"{self.api_url}{quote(path, safe='/')}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return trim_response(response.json())

    def get_paginated(
        self,
        path: str,
        params: typing.Optional[dict] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """GET a paginated REST API endpoint. Returns a single page of results."""
        request_params = dict(params or {})
        request_params["page"] = page
        request_params["page_size"] = page_size

        data = self.get(path, params=request_params)

        # Secoda paginates with {results, count, next, previous}
        results = data.get("results", data if isinstance(data, list) else [])
        count = data.get("count", data.get("total", len(results)))

        total_pages = math.ceil(count / page_size) if count > 0 else 1

        return {
            "results": results,
            "total_count": count,
            "page": page,
            "total_pages": total_pages,
        }
