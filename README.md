# Composio app research agent: 100 apps, toolkit-ready?

An agent that researches whether an app can become a Composio toolkit, along with its output for the 100 apps in the
take-home brief and the loops that verified that output.

**Headline:** 67 of 100 apps can be built as toolkits today (self-serve credentials and a documented API).
24 more are buildable with a caveat (paid plan, app review or self-hosting). 7 need outreach and 2 have no public API.
Auth is not the bottleneck (45 apps offer both OAuth2 and a key or token). The blockers are paid plans, partner or
customer-only access, and app review. 57 apps already ship an official MCP server.

Accuracy on a held-out sample: **96%** for the final data, against 88% for the model-only first pass (see `data/verification.json`).

- Case study page: `site/index.html` (live: https://composio-app-research.vercel.app), a single self-contained file with the dataset embedded as JSON
- Dataset: `data/final.json`, one object per app with evidence URLs, the pass-1 values and a change log
- Open questions for a human: `HUMAN_CHECKS.md`

## Repo layout

```
agent/
  apps.csv            the 100 apps from the brief (name, category, website hint)
  schema.py           research schema + the rules that derive verdict and main blocker
  research_agent.py   the agent (per-app research protocol, MCP-registry check, Composio catalog check)
  verify.py           verification loops: rules, sampling, scoring, human queue
  build_page.py       renders site/index.html from data/
data/
  pass1_model_only.psv     first pass, model knowledge only, written BEFORE any lookup (the baseline)
  pass2_grounded.json      second pass, grounded in vendor docs (built by build_pass2.py)
  verification.json        L2 stratified sample + L4 held-out sample, truth per field, scores
  final.json / patterns.json   pass 2 + verified fixes, plus the aggregates shown on the page
  l1_rules_report.txt      output of the rule checks
  notes_grounded.psv       raw research notes taken during the run
  build_*.py               scripts that rebuild every data file deterministically
site/
  template.html, index.html
HUMAN_CHECKS.md            8 questions the agent could not settle
```

## How the agent works

For each app it runs one fixed protocol (`research_agent.py`):

1. **Discover** the vendor's docs domain. The brief's hint domain wins ties, and the agent checks for name collisions
   (for example consensus.app vs goconsensus.com).
2. **Read three different pages**: the auth page, the pricing or "get API access" page, and the MCP/AI page.
3. **Extract** into a fixed JSON schema (`schema.py`). Each field needs a URL and a short quote from the vendor's own domain.
4. **MCP registry check.** The official MCP Registry (`registry.modelcontextprotocol.io`) is queried. A server counts as
   *official* only if its namespace matches the vendor's domain (`com.airtable/...`) or GitHub org.
5. **Composio catalog check.** Is there already a toolkit page for the app?
6. **Derive** the verdict and main blocker with code rules, not model judgment, so identical facts always give identical verdicts.

Two backends:

- `--backend anthropic` (default): Claude with the server-side `web_search` and `web_fetch` tools.
- `--backend composio`: the **Composio SDK** runs the web I/O (search and scrape tools via `composio.tools.execute`) and
  Claude only extracts. Set the tool slugs with `COMPOSIO_SEARCH_TOOL` / `COMPOSIO_FETCH_TOOL`.

## Run it

```bash
pip install anthropic composio
export ANTHROPIC_API_KEY=sk-...            # COMPOSIO_API_KEY too for --backend composio

python agent/research_agent.py --dry-run               # shows the plan, no network
python agent/research_agent.py --ids 1-100             # full run  -> data/runs/latest.jsonl
python agent/research_agent.py --ids 4,34,92           # re-run a few apps

python agent/verify.py rules  data/final.json          # L1 rule checks
python agent/verify.py sample data/final.json --seed 2026 --per-cat 3
python agent/verify.py score  data/verification.json   # accuracy table
python agent/verify.py queue  data/final.json          # human checklist

# rebuild data + page from the recorded run
cd data && python build_pass2.py && python build_verification.py && python build_final.py \
        && python build_holdout.py && python build_final.py && cd ..
python agent/build_page.py --repo https://github.com/<you>/composio-app-research
```

**How this particular run was produced.** The dataset in `data/` was produced with Claude as the agent runtime, following
this protocol in an interactive agent session with web search and fetch tools. Every fetch was a separate, logged tool
call, and the notes are in `data/notes_grounded.psv`. `research_agent.py` packages the same protocol to run headless with
your own keys. A fresh run will differ slightly because vendor docs change.

## Verification

| Loop | What it does | Result |
|---|---|---|
| L1 rules | Evidence on the vendor's domain, verdict matches the rule, no unknowns, "no MCP" needs two sources, URL re-read | 52 flags: 5 vendor-owned alternate doc domains whitelisted, 2 real issues sent to humans, 34 "no MCP" claims marked low-confidence, 11 URLs not re-read |
| L2 stratified sample | 30 apps (3 per category, seed 2026), re-checked against a *different* primary page | Pass 1: 76/84 (90.5%). Pass 2: 79/84 (94.0%). Errors fixed in 4 apps |
| L3 negative re-check | "No MCP" claims re-checked on the vendor's MCP page | 3 of 6 flipped (Attio, Brex official; Fathom docs-only) |
| L4 held-out | 10 untouched apps (seed 7), scored on the **final** data | Final: 24/25 (96%). Pass 1: 22/25 (88%) |
| L5 catalog | "Not in Composio" rows looked up one by one | 4 of 16 were actually listed and were fixed |

Fields scored: access gate (self-serve / paid / approval / sales-none), MCP status (official / docs-only / none) and
verdict. Auth method matched the docs for 30 of 30 apps in both passes.

**The main lesson.** A page that doesn't mention MCP is not evidence that there isn't one. 7 of 21 re-checked
"no MCP" claims were wrong. The protocol now requires a dedicated MCP-page check plus a registry lookup before writing
"none", and the 39 remaining "none found" rows should be read as "not found yet".

## Where a human was needed

- JS-only docs (Ramp, QuickBooks, the brief's Notion page): the fetch tool got an empty shell.
- Pages that block bots (systeme.io API reference, Podio pricing, Coda developers).
- Docs behind a login or contract (PitchBook, DealCloud, Gladly, Otter Enterprise API).
- Name collisions (Consensus, fanbasis, iPayX).
- Judging docs-only vs action MCP servers (Plain, Vonage, Fathom, BigCommerce, Plaid).
- Triaging rule flags and confirming catalog misses. See `HUMAN_CHECKS.md` for the 8 open questions.

## Field definitions

`access`: FREE (free plan, dev account or OSS) · TRIAL (self-serve trial or credits) · PAID (must pay first) ·
REVIEW (production needs vendor or app review, or KYC) · PARTNER (contract, customer-only, book-a-call) · NONE (no public API).
`mcp`: OFFICIAL (vendor-hosted, vendor GitHub org or registry vendor namespace) · DOCS_ONLY · NONE_FOUND.
`verdict`: Ready now · Buildable w/ caveat · Needs outreach · Not buildable today (derived in `schema.py`).
`status`: verified in sample · doc read · canonical URL (not re-read) · needs human check.
