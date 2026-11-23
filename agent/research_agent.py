"""Research agent: turns an app name into a structured, evidence-backed toolkit-feasibility row.

Per app it runs a fixed protocol (the same one used to produce data/pass2_grounded.json):

  1. DISCOVER   find the vendor's developer docs (search; the brief's hint domain is a strong prior)
  2. READ       fetch the auth page, the pricing/plans page and the MCP/AI page (three different pages)
  3. EXTRACT    fill RESEARCH_SCHEMA; every field needs a URL + short quote from the vendor's own domain
  4. MCP CHECK  query the official MCP Registry; "official" only if the namespace matches the vendor domain
  5. CATALOG    check whether Composio already lists a toolkit for the app
  6. DERIVE     verdict + main blocker come from rules in schema.py, not from the model

Backends
  --backend anthropic  (default) Claude with server-side web_search + web_fetch tools.
  --backend composio   Composio SDK executes search/scrape tools (e.g. Composio Search, Firecrawl)
                       and Claude only does extraction. Set the tool slugs in COMPOSIO_TOOLS.

Usage
  export ANTHROPIC_API_KEY=...            # required
  export COMPOSIO_API_KEY=...             # only for --backend composio
  python agent/research_agent.py --ids 1-100 --out data/runs/latest.jsonl
  python agent/research_agent.py --ids 4,34,92 --out data/runs/spot.jsonl   # re-run a few apps
  python agent/research_agent.py --dry-run                                   # no network, prints the plan
"""
from __future__ import annotations

import argparse, csv, json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schema import RESEARCH_SCHEMA, verdict, main_blocker  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.getenv("RESEARCH_MODEL", "claude-sonnet-5-5")          # any tool-use capable Claude model
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 6}
WEB_FETCH_TOOL = {"type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 6}
COMPOSIO_TOOLS = {  # verify slugs in the Composio catalog for your account before using --backend composio
    "search": os.getenv("COMPOSIO_SEARCH_TOOL", "COMPOSIO_SEARCH_SEARCH"),
    "fetch": os.getenv("COMPOSIO_FETCH_TOOL", "FIRECRAWL_SCRAPE"),
}

PROTOCOL = """You are a toolkit-feasibility researcher at Composio. Research ONE app and return JSON only.

App: {name}   Category: {category}   Hint from the brief: {hint}

Protocol (follow in order):
1. Identify the vendor and its developer-docs domain. The hint domain wins ties. Beware name collisions
   (e.g. consensus.app vs goconsensus.com) - if two companies share the name, use the one matching the hint.
2. Read THREE different pages: (a) the auth/authentication page, (b) the pricing/plans or
   "get API access" page, (c) the vendor's MCP / AI-agents page (or search "<app> MCP server").
3. Fill the schema. Definitions:
   access: FREE (free plan/dev account/OSS) | TRIAL (self-serve trial or free credits, no sales call) |
           PAID (must pay first) | REVIEW (start free but production needs vendor/app review) |
           PARTNER (contract, customer-only tenant, book-a-call) | NONE (no public API).
   mcp: OFFICIAL only if the vendor documents/hosts it or it lives in the vendor's GitHub org.
        DOCS_ONLY if the vendor MCP only searches documentation. NONE_FOUND otherwise.
4. RULES: Never mark NONE_FOUND just because one page is silent - you must have checked the vendor's
   MCP/AI page or searched for it. Evidence must come from the vendor's own domain (or its GitHub org);
   third-party blogs only as a last resort and say so in the note. If you could not verify a field,
   say "unverified" in its note instead of guessing.
Return ONLY a JSON object matching this schema:
{schema}"""


# ----------------------------------------------------------------------------- helpers
def http_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": "composio-app-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def vendor_domain(hint: str) -> str:
    m = re.search(r"([a-z0-9-]+\.)+[a-z]{2,}", hint.lower())
    host = m.group(0) if m else ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def mcp_registry_check(name: str, domain: str) -> dict:
    """Official MCP Registry lookup. Namespaces are reverse-DNS and DNS/GitHub-verified by the registry,
    so com.<vendor>/... or io.github.<vendor-org>/... is strong evidence of a first-party server."""
    q = urllib.parse.quote(name.split(" (")[0])
    try:
        data = http_json(f"https://registry.modelcontextprotocol.io/v0/servers?search={q}&limit=50")
    except Exception as e:  # registry down / blocked -> unknown, never "none"
        return {"status": "unknown", "error": str(e)}
    label = domain.split(".")[0] if domain else name.lower().split()[0]
    rev = ".".join(reversed(domain.split("."))) if domain else ""
    official = []
    for item in data.get("servers", []):
        s = item.get("server", item)
        ns = s.get("name", "")
        if (rev and ns.startswith(rev + "/")) or ns.lower().startswith(f"io.github.{label}"):
            remotes = [r.get("url") for r in s.get("remotes", []) or []]
            official.append({"name": ns, "remotes": remotes})
    return {"status": "found" if official else "none_in_registry", "official": official,
            "third_party_entries": len(data.get("servers", [])) - len(official)}


def composio_catalog_check(slug_guess: str) -> str:
    """Does Composio already list a toolkit? Uses the public toolkit page (200 = listed)."""
    for slug in (slug_guess, slug_guess + "_mcp"):
        try:
            urllib.request.urlopen(f"https://composio.dev/toolkits/{slug}.md", timeout=15)
            return "MCP" if slug.endswith("_mcp") else "Y"
        except Exception:
            continue
    return "N"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().split(" (")[0]).strip("_")


# ----------------------------------------------------------------------------- backends
def research_with_anthropic(app: dict) -> dict:
    import anthropic  # pip install anthropic
    client = anthropic.Anthropic()
    prompt = PROTOCOL.format(name=app["name"], category=app["category"], hint=app["hint"],
                             schema=json.dumps(RESEARCH_SCHEMA))
    msg = client.messages.create(
        model=MODEL, max_tokens=4000,
        tools=[WEB_SEARCH_TOOL, WEB_FETCH_TOOL],
        extra_headers={"anthropic-beta": "web-fetch-2025-09-10"},
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return parse_json(text)


def research_with_composio(app: dict) -> dict:
    """Composio does the web I/O (search + scrape); Claude only extracts."""
    from composio import Composio  # pip install composio
    import anthropic
    cx = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
    uid = os.getenv("COMPOSIO_USER_ID", "default")

    def run(tool, args):
        return cx.tools.execute(tool, user_id=uid, arguments=args, dangerously_skip_version_check=True)

    pages = []
    for q in (f"{app['name']} API authentication", f"{app['name']} API pricing plan access",
              f"{app['name']} MCP server"):
        res = run(COMPOSIO_TOOLS["search"], {"query": q})
        urls = re.findall(r"https?://[^\s\"']+", json.dumps(res))[:2]
        for u in urls:
            page = run(COMPOSIO_TOOLS["fetch"], {"url": u})
            pages.append({"url": u, "content": json.dumps(page)[:12000]})
    prompt = PROTOCOL.format(name=app["name"], category=app["category"], hint=app["hint"],
                             schema=json.dumps(RESEARCH_SCHEMA))
    prompt += "\n\nPages already fetched for you (use only these as evidence):\n" + json.dumps(pages)
    msg = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=4000,
                                                messages=[{"role": "user", "content": prompt}])
    return parse_json("".join(b.text for b in msg.content if b.type == "text"))


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("model returned no JSON")
    return json.loads(m.group(0))


# ----------------------------------------------------------------------------- main loop
def load_apps(ids: str) -> list[dict]:
    apps = list(csv.DictReader(open(ROOT / "agent" / "apps.csv")))
    want: set[int] = set()
    for part in ids.split(","):
        a, _, b = part.partition("-")
        want |= set(range(int(a), int(b or a) + 1))
    return [a for a in apps if int(a["id"]) in want]


def research_one(app: dict, backend: str) -> dict:
    row = research_with_anthropic(app) if backend == "anthropic" else research_with_composio(app)
    dom = vendor_domain(app["hint"])
    reg = mcp_registry_check(app["name"], dom)
    if reg["status"] == "found" and row.get("mcp") != "OFFICIAL":       # registry overrides a negative
        row["mcp"], row["mcp_note"] = "OFFICIAL", f"Registry: {reg['official'][0]['name']}"
    row.update(id=int(app["id"]), name=app["name"], cat=app["category"], hint=app["hint"],
               mcp_registry=reg, composio=composio_catalog_check(slugify(app["name"])))
    row["verdict"], row["main_blocker"] = verdict(row), main_blocker(row)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="1-100")
    ap.add_argument("--backend", choices=["anthropic", "composio"], default="anthropic")
    ap.add_argument("--out", default=str(ROOT / "data" / "runs" / "latest.jsonl"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apps = load_apps(args.ids)
    if args.dry_run:
        for a in apps:
            print(f"[plan] #{a['id']:>3} {a['name']:<28} domain={vendor_domain(a['hint']) or '?':<22} "
                  f"slug={slugify(a['name'])}")
        print(f"{len(apps)} apps; backend={args.backend}; model={MODEL}")
        return
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "a") as f:
        for a in apps:
            for attempt in range(3):
                try:
                    row = research_one(a, args.backend)
                    break
                except Exception as e:  # keep going; failures land in the human queue
                    row = {"id": int(a["id"]), "name": a["name"], "error": str(e), "needs_human": True}
                    time.sleep(2 * (attempt + 1))
            f.write(json.dumps(row) + "\n"); f.flush()
            print(f"#{a['id']:>3} {a['name']:<28} {row.get('access','ERR'):<8} {row.get('mcp','')}")


if __name__ == "__main__":
    main()
