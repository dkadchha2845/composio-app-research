"""Shared schema + deterministic rules used by every stage of the pipeline.

Keeping the rules in code (not in the LLM prompt) is deliberate: the verdict and the
"main blocker" are *derived* from the researched facts, so two apps with the same facts
always get the same verdict, and a reviewer can audit the logic in one place.
"""
from __future__ import annotations

ACCESS = {
    "FREE":    "Self-serve (free)",      # free plan / free dev account / OSS
    "TRIAL":   "Self-serve (trial)",     # time-limited or credit-limited trial, no sales call
    "PAID":    "Paid plan",              # must pay before you can get credentials
    "REVIEW":  "Approval / app review",  # self-serve start, but production needs vendor review
    "PARTNER": "Sales / partner gate",   # contract, customer-only tenant, book-a-call
    "NONE":    "No public API",
}
MCP = {"OFFICIAL": "Official MCP", "DOCS_ONLY": "Docs-only MCP", "NONE_FOUND": "None found"}

# JSON schema the research agent must fill (one object per app).
RESEARCH_SCHEMA = {
    "type": "object",
    "required": ["what", "auth", "access", "access_note", "api", "breadth", "mcp", "mcp_note", "blocker", "evidence"],
    "properties": {
        "what": {"type": "string", "description": "What the app does, one line, <= 12 words"},
        "auth": {"type": "array", "items": {"type": "string"},
                 "description": "Auth methods, e.g. OAuth2, API key, Basic, Bearer token, JWT, OAuth1, None"},
        "access": {"enum": list(ACCESS)},
        "access_note": {"type": "string", "description": "How a developer actually gets credentials, with plan names"},
        "api": {"type": "string", "description": "REST | GraphQL | REST+GraphQL | CLI | MCP-only | None"},
        "breadth": {"enum": ["Broad", "Medium", "Narrow", "None"]},
        "mcp": {"enum": list(MCP)},
        "mcp_note": {"type": "string", "description": "Server URL / repo and auth, or what was checked"},
        "blocker": {"type": "string", "description": "Main thing that stops an agent toolkit today, or ''"},
        "evidence": {"type": "array", "items": {"type": "object", "required": ["field", "url", "quote"],
                     "properties": {"field": {"type": "string"}, "url": {"type": "string"},
                                    "quote": {"type": "string", "description": "<= 25 words copied from the page"}}}},
    },
}


def verdict(row: dict) -> str:
    """Buildability verdict, derived (never free-typed by the model)."""
    a, api, blk = row["access"], row.get("api", ""), row.get("blocker", "").lower()
    if a == "NONE":
        return "Not buildable today"
    if a == "PARTNER":
        return "Needs outreach"
    if a in ("PAID", "REVIEW") or api.startswith("CLI") or "enterprise" in api.lower() \
            or "per-store" in blk or "per-instance" in blk:
        return "Buildable w/ caveat"
    return "Ready now"


def main_blocker(row: dict) -> str:
    a = row["access"]
    if a == "NONE":
        return "No public API"
    if a == "PARTNER":
        return "Sales/partner or customer-only access"
    if a == "REVIEW":
        return "App review / approval tier"
    if a == "PAID":
        return "Paid plan required to test"
    if row.get("api", "").startswith("CLI"):
        return "No API (local CLI)"
    blk = row.get("blocker", "").lower()
    if "per-store" in blk or "per-instance" in blk:
        return "Self-hosted / per-instance URL"
    return "—"
