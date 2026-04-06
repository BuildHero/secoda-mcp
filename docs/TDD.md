# TDD: Secoda MCP Server — Custom Fork

| Field       | Value                                      |
|-------------|--------------------------------------------|
| Author      | Data Engineering                           |
| Date        | 2026-03-10                                 |
| Status      | In Review                                  |
| Upstream    | [secoda/secoda-mcp](https://github.com/secoda/secoda-mcp) |

---

## Problem Statement

The official Secoda MCP server proxies all tool calls through a single backend endpoint (`/ai/mcp/tools/call/`), exposing only **6 tools**: `run_sql`, `search_data_assets`, `search_documentation`, `retrieve_entity`, `entity_lineage`, and `glossary`.

This has several limitations:

1. **Limited tool coverage.** Many first-class Secoda REST API resources — collections, documents, integrations, tables, questions, tags, and custom properties — have no MCP tool, so LLM agents cannot browse or list catalog content without falling back to keyword search.
2. **No error handling.** HTTP errors, timeouts, and connection failures raise unhandled Python exceptions that crash the tool call instead of returning a structured error the LLM can reason about.
3. **No input validation.** Entity ID parameters are interpolated directly into URL paths with no format check, creating a path-traversal risk.
4. **No connection pooling.** Each tool call creates a new `requests.post()` with inline headers instead of reusing an HTTP session.
5. **Verbose responses.** Raw API responses include internal metadata fields (`bookmarked_by`, `multiplayers`, `workspace_id`, etc.) that consume LLM context tokens without adding value.

## Solution

Fork the official server locally and extend it with a **dual-path architecture**:

- **Proxy path** — retain the original 6 tools that call Secoda's MCP backend (search, SQL, and lineage have no direct REST equivalent).
- **Direct REST path** — add 10 new tools that call the Secoda REST API directly for browsable and listable resources.

Both paths share a centralized HTTP client with session reuse, structured error handling, response trimming, and input validation.

### New Tools (Direct REST)

| Tool                    | REST Endpoint                            | Purpose                              |
|-------------------------|------------------------------------------|--------------------------------------|
| `list_collections`      | `GET /collection/collections`            | Browse collections, filter by title  |
| `get_collection`        | `GET /collection/collections/{id}`       | Read a collection's detail + resources |
| `list_documents`        | `GET /document/documents`                | Browse documents, filter by title    |
| `get_document`          | `GET /document/documents/{id}`           | Read full document content           |
| `list_integrations`     | `GET /integration/integrations`          | Discover data source integrations    |
| `list_tables`           | `GET /table/tables`                      | Browse tables, filter by integration/title |
| `list_questions`        | `GET /question/questions`                | Browse Q&A entries                   |
| `get_question`          | `GET /question/questions/{id}` + replies | Read question with answers           |
| `list_tags`             | `GET /tag/tags`                          | Browse workspace tags                |
| `list_custom_properties`| `GET /resource/all_v2/custom_properties` | Browse custom field definitions      |

Total tool count: **6 proxy + 10 REST = 16 tools**.

## Architecture

```
server.py  (orchestrator)
  |
  |-- creates SecodaClient(API_URL, API_TOKEN)
  |
  |-- register_proxy_tools(mcp, client)        # tools_proxy.py
  |     |-- run_sql, search_data_assets,       # 6 tools
  |     |   search_documentation,
  |     |   retrieve_entity, entity_lineage,
  |     |   glossary
  |     |
  |     +-> client.call_mcp_tool()
  |           +-> POST /ai/mcp/tools/call/     # Secoda MCP backend
  |
  |-- register_rest_tools(mcp, client)         # tools_rest.py
  |     |-- list_collections, get_collection,  # 10 tools
  |     |   list_documents, get_document,
  |     |   list_integrations, list_tables,
  |     |   list_questions, get_question,
  |     |   list_tags, list_custom_properties
  |     |
  |     +-> client.get() / client.get_paginated()
  |           +-> GET /api/v1/{resource}       # Secoda REST API
  |
  +-- prompt.py  (system prompt for all 16 tools)

client.py  (shared infrastructure)
  |-- SecodaClient        — requests.Session, auth headers, 30s timeout, URL path encoding
  |-- safe_json_call()    — wraps any callable, catches HTTP/connection/timeout/validation/unexpected errors
  |-- trim_response()     — strips noisy metadata fields from API responses (depth-limited to 50)
  +-- validate_id()       — UUID regex check to prevent path traversal
```

## Key Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Dual-path: proxy + direct REST** | Proxy tools rely on Secoda's MCP backend for features with no public REST equivalent (semantic search, SQL execution, lineage graph). New browsable resources use direct REST to avoid the proxy's limited tool set. |
| 2 | **Centralized `SecodaClient`** | Single `requests.Session` provides connection pooling, consistent auth headers, and a 30-second timeout across all tools. Eliminates duplicated HTTP setup. Startup validates `API_TOKEN` is set. |
| 3 | **`safe_json_call` error wrapper** | Every tool call is wrapped so HTTP errors, timeouts, connection failures, and validation errors return structured JSON (`{"error": "...", "detail": "..."}`) instead of crashing. A catch-all `except Exception` handler ensures no unhandled exception ever crashes the server. |
| 4 | **Response trimming (REST path only)** | Strips 12 internal metadata fields (`bookmarked_by`, `multiplayers`, `workspace_id`, `entity_chat_context`, etc.) from direct REST responses to reduce LLM token consumption. Note: proxy tool responses are not trimmed, as Secoda's MCP backend controls their format. Recursion is depth-limited to 50 to prevent stack overflow on deeply nested responses. |
| 5 | **Input sanitization** | `validate_id()` checks that ID parameters match UUID format before use. Additionally, `client.get()` applies `urllib.parse.quote()` to all URL paths, preventing path-traversal and injection attacks. |
| 6 | **Modular tool registration** | `tools_proxy.py` and `tools_rest.py` are separate modules with `register_*` functions called by `server.py`. This keeps the proxy and REST tools independently testable and avoids a monolithic server file. |
| 7 | **Graceful degradation** | Composite tool calls (e.g., `get_question` fetching replies) catch sub-request failures and attach error metadata instead of failing the entire call. |

## Files Changed

| File | Status | Description |
|------|--------|-------------|
| `client.py` | **New** | `SecodaClient` class with shared session, pagination, error handling, response trimming, and ID validation |
| `tools_proxy.py` | **New** | Original 6 proxy tools extracted from `server.py` into their own module |
| `tools_rest.py` | **New** | 10 new tools calling Secoda REST API directly |
| `server.py` | **Modified** | Simplified to an orchestrator — creates client, registers both tool modules. Added startup validation for `API_TOKEN`. |
| `prompt.py` | **Modified** | Expanded system prompt documenting all 16 tools organized by category (Search, Browse, Details, Data Access) with usage patterns. Removed two pitfalls from the original ("Terminology Conflation", "Context Neglect"); added BROWSE BY CATEGORY, USAGE GUIDE, and ID chaining guidance. |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Secoda REST API changes could break direct tools | Direct tools use stable v1 endpoints; proxy tools are unaffected since they delegate to Secoda's backend |
| New tools increase LLM tool-selection complexity | System prompt groups tools by purpose and includes a usage guide to steer the LLM |
| Upstream repo merges could conflict | Changes are modular (new files + minimal edits to existing files), making merge conflicts unlikely |

## Verification

1. Start the server: `python server.py`
2. Connect via an MCP client (Claude Desktop, Cursor, etc.)
3. Verify original proxy tools still work: `search_data_assets(query="revenue")`, `glossary()`
4. Verify new REST tools: `list_integrations()`, `list_collections()`, `get_document({id})`
5. Verify error handling: disconnect network and confirm tools return JSON error objects instead of crashing
6. Verify ID validation: pass a non-UUID string to `get_collection()` and confirm a validation error is returned
