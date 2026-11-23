"""Verification loops.

  L1 rules       deterministic checks on every row (evidence domain, verdict consistency, unknowns,
                 name collisions, "negative MCP needs two sources"). Runs offline.
  L2 sample      stratified random sample (3 per category, fixed seed) re-checked against a *different*
                 primary page than the one used for extraction; scores pass 1 vs pass 2 per field.
  L3 negatives   every "no MCP" claim whose only evidence was a silent page gets a second, targeted check.
  L4 held-out    a fresh sample never touched by L2/L3, scored against the FINAL data -> the honest number.
  Human queue    anything the agent could not verify (JS-only docs, robots.txt, gated docs, ambiguity).

Usage
  python agent/verify.py rules   data/final.json          # L1 report
  python agent/verify.py sample  data/final.json --seed 2026 --per-cat 3
  python agent/verify.py score   data/verification.json   # prints the accuracy table
  python agent/verify.py queue   data/final.json          # human checklist (markdown)
"""
from __future__ import annotations

import argparse, json, random, sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from schema import verdict  # noqa: E402

THIRD_PARTY_OK = ("registry.modelcontextprotocol.io", "github.com")  # vendor org checked separately
# Parent-company / docs domains that count as "the vendor's own" (learned the hard way during L1).
PARENT = {"Threads (Meta)": ["facebook.com"], "Meta Ads": ["facebook.com"], "WhatsApp Business": ["facebook.com"],
          "SendGrid": ["twilio.com"], "Jira": ["atlassian.com"], "QuickBooks": ["intuit.com"],
          "Magento (Adobe Commerce)": ["adobe.com"], "Paygent Connect": ["nmi.com"], "NotebookLM": ["google.com"],
          "LinkedIn Ads": ["microsoft.com"], "Amazon Selling Partner": ["amazon"], "GoHighLevel": ["gohighlevel.com", "stoplight.io"],
          "Lark (Larksuite)": ["larksuite.com"], "DealCloud": ["dealcloud.com"], "YouTube Transcript": ["transcriptapi.com"],
          "Salesforce Commerce Cloud": ["salesforce.com"], "Neo4j": ["neo4j.com"], "Clay": ["clay.com"], "Grain": ["grain.com"],
          "Fathom": ["fathom.ai"], "Twenty": ["twenty.com"], "Ecwid": ["ecwid.com"], "Monday.com": ["monday.com"],
          # L1 triage: vendor-owned alternate docs hosts (accepted after review)
          "Pipedrive": ["pipedrive.readme.io"], "Front": ["frontapp.com"], "Slack": ["slack.dev"],
          "Harvest": ["getharvest.com"], "Binance": ["binance.com"]}


def allowed_hosts(r, hints):
    import re
    h = hints.get(r["id"], "")
    m = re.search(r"([a-z0-9-]+\.)+[a-z]{2,}", h.lower())
    base = ".".join(m.group(0).split(".")[-2:]) if m else ""
    return [x for x in [base] + PARENT.get(r["name"], []) if x]


def host(u: str) -> str:
    return urlparse(u).netloc.lower().removeprefix("www.")


def rules(rows: list[dict]) -> list[dict]:
    import csv
    hints = {int(a["id"]): a["hint"] for a in csv.DictReader(open(Path(__file__).parent / "apps.csv"))}
    flags = []
    names = defaultdict(list)
    for r in rows:
        names[r["name"].split()[0].lower()].append(r["name"])
        ev = [e if isinstance(e, str) else e.get("url", "") for e in r.get("evidence", [])]
        hosts = [host(u) for u in ev if u.startswith("http")]
        ok = allowed_hosts(r, hints) or [r["name"].lower().split()[0]]
        if not hosts:
            flags.append((r, "R1", "no evidence URL"))
        elif not any(any(o in h for o in ok) or h.endswith(THIRD_PARTY_OK) for h in hosts):
            flags.append((r, "R1", f"evidence not on vendor domain: {hosts[0]}"))
        if r.get("verdict") and r["verdict"] != verdict(r):
            flags.append((r, "R2", f"verdict '{r['verdict']}' != rule '{verdict(r)}'"))
        if "Unknown" in r.get("auth", []) and r["access"] != "NONE":
            flags.append((r, "R3", "auth unknown but API claimed"))
        if r.get("mcp") == "NONE_FOUND" and "registry" not in (r.get("mcp_note", "") + " ".join(ev)).lower() \
                and "docs" not in r.get("mcp_note", "").lower():
            flags.append((r, "R4", "negative MCP claim has a single (silent-page) source → low confidence"))
        if r.get("status") == "canonical URL (not re-read)":
            flags.append((r, "R5", "evidence URL known but not re-read in this run"))
    return [dict(id=r["id"], name=r["name"], rule=k, msg=m) for r, k, m in flags]


def sample(rows, seed=2026, per_cat=3, exclude=()):
    random.seed(seed)
    by = defaultdict(list)
    for r in rows:
        if r["id"] not in exclude:
            by[r["cat"]].append(r)
    return sorted(i["id"] for c in by.values() for i in random.sample(c, min(per_cat, len(c))))


def score(v: dict):
    s = v["score"]
    print("L2 stratified sample (n=30)")
    for f in s:
        print(f"  {f:<8} pass1 {s[f]['p1'][0]}/{s[f]['p1'][1]}   pass2 {s[f]['p2'][0]}/{s[f]['p2'][1]}")
    h = v["holdout"]["score"]
    print(f"L4 held-out (n=10): pass1 {h['p1'][0]}/{h['p1'][1]}   final {h['final'][0]}/{h['final'][1]}")


def queue(rows):
    print("# Human verification queue\n")
    for r in rows:
        if r.get("human_question"):
            print(f"- [ ] **{r['name']}** — {r['human_question']}  \n  start at: {r['evidence'][0]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["rules", "sample", "score", "queue"])
    ap.add_argument("path")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--per-cat", type=int, default=3)
    a = ap.parse_args()
    data = json.load(open(a.path))
    if a.cmd == "rules":
        fl = rules(data)
        for f in fl:
            print(f"{f['rule']} #{f['id']:>3} {f['name']:<26} {f['msg']}")
        print(f"\n{len(fl)} flags on {len(data)} rows")
    elif a.cmd == "sample":
        print(sample(data, a.seed, a.per_cat))
    elif a.cmd == "score":
        score(data)
    else:
        queue(data)
