"""Render site/index.html from the data files (single self-contained page, data embedded).

  python agent/build_page.py [--repo https://github.com/<you>/composio-app-research]
"""
import argparse, json, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="")
    ap.add_argument("--date", default=datetime.date.today().strftime("%d %b %Y"))
    a = ap.parse_args()

    final = json.load(open(D / "final.json"))
    pats = json.load(open(D / "patterns.json"))
    ver = json.load(open(D / "verification.json"))

    keep = ["id", "name", "cat", "what", "auth", "auth_family", "access", "gate", "access_note", "api", "breadth",
            "mcp", "mcp_note", "blocker", "main_blocker", "verdict", "composio", "evidence", "status",
            "human_question", "pass1", "changes", "grounding"]
    data = [{k: r.get(k) for k in keep} for r in final]

    # every miss across loops, newest truth wins
    misses = []
    for r in ver["rows"]:
        for f in ("gate", "mcp", "verdict"):
            t = r[f + "_truth"]
            if t and (r["p1"][f] != t or r["p2"][f] != t):
                misses.append(dict(name=r["name"], field=f, p1=r["p1"][f], p2=r["p2"][f], truth=t,
                                   url=r["verify_url"], status="fixed (L2)" if r["p2"][f] != t else "pass 2 already right"))
    for r in ver["holdout"]["rows"]:
        for f in ("gate", "mcp", "verdict"):
            t = r[f + "_truth"]
            if t and (r["p1"][f] != t or r["final"][f] != t):
                misses.append(dict(name=r["name"], field=f, p1=r["p1"][f], p2=r["final"][f], truth=t,
                                   url=r["verify_url"], status="miss on held-out → fixed after" if r["final"][f] != t else "final already right"))
    for n, f, p1, p2, t, u in [("Attio", "mcp", "official", "none", "official", "https://docs.attio.com/mcp/overview"),
                               ("Brex", "mcp", "none", "none", "official", "https://developer.brex.com/"),
                               ("Fathom", "mcp", "none", "none", "docs-only", "https://developers.fathom.ai/mcp")]:
        misses.append(dict(name=n, field=f, p1=p1, p2=p2, truth=t, url=u, status="fixed (L3 negative re-check)"))

    loops = [
        ("L1 · Rules on all 100 rows (code)", "Checks: evidence on the vendor's own domain, verdict matches the rule, no unknowns, "
         "'no MCP' backed by two sources, URL re-read in this run. First run: 52 flags. 5 were vendor-owned alternate docs "
         "domains (readme.io, slack.dev, frontapp.com, getharvest.com, binance.com), so those were whitelisted. 2 were real "
         "(fanbasis has no docs; Otter rests on a third-party source) and went to the human queue. 34 'no MCP' claims "
         "rest on one silent page, so they're marked low-confidence."),
        ("L2 · Stratified sample, 30 apps", "Re-read a different primary page (pricing, MCP or registry) for 3 apps per category. "
         f"Pass 1 scored {sum(ver['score'][f]['p1'][0] for f in ver['score'])}/84 and pass 2 "
         f"{sum(ver['score'][f]['p2'][0] for f in ver['score'])}/84. It found pass-2 errors in 4 apps (Aircall, Vonage, GoHighLevel, WooCommerce) and fixed them. 4 apps couldn't be verified and went to humans."),
        ("L3 · Re-check of 'no MCP' claims", "Because 2 of the 4 L2 errors were false 'no MCP' claims, 6 more negatives "
         "were re-checked on the vendor's MCP page. 3 flipped (Attio and Brex are official, Fathom is docs-only), 2 held "
         "(Zendesk, Meta), and 1 page couldn't be reached (Pipedrive)."),
        ("L4 · Held-out sample, 10 apps", f"Fresh apps never touched by L2 or L3, scored on the final data: "
         f"{ver['holdout']['score']['final'][0]}/{ver['holdout']['score']['final'][1]}. The one miss (Twenty has an MCP) "
         "is the same error type, so it was fixed and kept as a stated residual risk."),
        ("L5 · Composio catalog look-ups", "The 'already in Composio?' column first came from one summarised read of the catalog page. "
         "Looking up 16 'not listed' apps one by one at docs.composio.dev/toolkits/<slug> found 4 were in fact listed "
         "(systeme.io, Reducto, GoHighLevel as 'Highlevel', Squarespace). Those were fixed. 'Not listed' now means no page at the slugs tried."),
    ]
    needs = [
        ("JS-only docs", "The fetch tool got an empty shell, so the docs need a real browser.", "Ramp, QuickBooks, the brief's own Notion page"),
        ("Bots blocked by robots.txt", "The page couldn't be fetched, so a secondary source or a human was used.", "systeme.io API reference, Podio pricing, Coda developers"),
        ("Docs behind a login or contract", "Some facts are only visible to customers.", "PitchBook, DealCloud, Gladly, Otter Enterprise API"),
        ("Name collisions", "Search returned a different company with the same name. The brief's hint domain decided which was meant.", "Consensus (consensus.app vs goconsensus.com), fanbasis (vs Fanbase or Fanvue), iPayX (vs iPay)"),
        ("Judgment: docs MCP or action MCP?", "'Has an MCP' can mean a docs search box. Each one was classified by hand.", "Plain, Vonage, Fathom, BigCommerce, Plaid"),
        ("Catalog look-up by slug", "A missing page under one slug isn't proof of absence (GoHighLevel is listed as 'highlevel'). A person should confirm before outreach.", "LiveAgent, Vonage, SE Ranking, Binance, WooCommerce"),
        ("Triaging rule flags", "Deciding whether a domain belongs to the vendor (slack.dev? readme.io?).", "Pipedrive, Front, Slack, Harvest, Binance"),
    ]
    meta = dict(patterns=pats, sample=ver["score"], holdout=ver["holdout"]["score"], loops=loops, misses=misses,
                needs=needs, schema=(ROOT / "agent" / "schema.py").read_text().split('RESEARCH_SCHEMA = ')[1].split('\n\n\n')[0],
                lesson="A silent page is not evidence of absence. When the agent read a page that didn't mention MCP, it "
                       "wrote 'no MCP'. On re-check, 7 of 21 such claims were wrong (5 had an official server, 2 a docs-only one). "
                       "The protocol now requires a dedicated MCP-page check plus a registry lookup before writing 'none'. "
                       "The 39 remaining 'none found' should be read as 'not found yet'.")
    ready = sum(r["verdict"] == "Ready now" for r in final)
    html = (ROOT / "site" / "template.html").read_text()
    js = lambda o: json.dumps(o, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("__DATA__", js(data)).replace("__META__", js(meta)).replace("BUILD_DATE", a.date)
    html = html.replace("68 of 100 apps", f"{ready} of 100 apps")
    if a.repo:
        html = html.replace("REPO_URL", a.repo).replace("REPO_LABEL", a.repo.replace("https://", ""))
    else:
        html = html.replace("git clone REPO_URL && cd composio-app-research", "cd composio-app-research   # unzip the repo")
        html = html.replace('<a id="repolink" href="REPO_URL">REPO_LABEL</a>', "composio-app-research (submitted alongside this page)")
    (ROOT / "site" / "index.html").write_text(html)
    print(f"site/index.html  {len(html)/1024:.0f} KB  ready={ready}  misses={len(misses)}")


if __name__ == "__main__":
    main()
