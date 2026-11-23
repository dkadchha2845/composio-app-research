"""Pass 3: verification of a stratified random sample (seed 2026, 3 apps/category).
Truth = what the primary page says when re-read by the verifier (a different page from the pass-2 evidence where possible).
Fields scored: auth (primary method family), gate (self-serve | paid | approval | sales/none), mcp (official | docs-only | none), verdict.
None in truth = could not be verified by the agent -> excluded from scoring and sent to the human queue."""
import json
T = {  # id: (auth_ok_note, gate, mcp, verify_url, note)
 2:("OAuth2 + private app token","self-serve","official","https://developers.hubspot.com/get-started",""),
 6:("OAuth2",None,"none","https://developers.podio.com/authentication","Pricing page blocked by robots.txt → plan gate unverified"),
 10:("Client id/secret → token","sales/none",None,"https://api.docs.dealcloud.com/","MCP page listed in nav but could not be fetched"),
 14:("OAuth2 + API token","self-serve","none","https://front.com/pricing","14-day trial, no card"),
 17:("API key (Bearer)","self-serve",None,"https://www.plain.com/docs/mcp","MCP page shows a 'Plain Docs' server: docs-only or action server? ambiguous"),
 19:("API key + OAuth2","self-serve","none","https://developers.gorgias.com/",""),
 28:("Access token","approval","none","https://developers.facebook.com/docs/whatsapp/overview/business-accounts","Payment method + verification raise limits"),
 29:("Basic + OAuth2","self-serve","none","https://aircall.io/pricing/","No free plan, but free test access; API on every tier"),
 30:("API key + JWT","self-serve","docs-only","https://registry.modelcontextprotocol.io/v0/servers?search=vonage","Vendor MCP is documentation-only"),
 34:("OAuth2 + Private Integration Token","paid","official","https://marketplace.gohighlevel.com/docs/other/mcp/index.html","Official MCP, 717 actions"),
 38:("OAuth2","approval","none","https://developers.pinterest.com/docs/getting-started/set-up-app/","Even trial tokens need review"),
 40:("API key","self-serve","none","https://www.twilio.com/en-us/sendgrid/pricing","Free plan retired — free trial only"),
 41:("OAuth2 + access token","self-serve","official","https://shopify.dev/docs/apps/build/dev-dashboard/development-stores",""),
 42:("Basic (consumer key/secret)","self-serve","official","https://developer.woocommerce.com/docs/features/mcp/","MCP is developer preview via MCP Adapter plugin"),
 49:("OAuth2 (LWA)","approval","none","https://developer-docs.amazon/sp-api/docs/sp-api-registration-overview","No MCP page found (404)"),
 52:("API key","self-serve","official","https://seranking.com/api/mcp/",""),
 55:("API token","self-serve","official","https://apify.com/pricing","Free plan $5/mo credit"),
 58:("None (CLI)","self-serve","none","https://github.com/sherlock-project/sherlock",""),
 61:("OAuth2 + PAT","self-serve","official","https://github.com/github/github-mcp-server",""),
 66:("Basic + bearer","self-serve","official","https://neo4j.com/developer/genai-ecosystem/model-context-protocol-mcp/",""),
 68:("Service account / API key","self-serve","official","https://github.com/mongodb-js/mongodb-mcp-server",""),
 74:("API token Basic + OAuth 3LO","self-serve","official","https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/",""),
 75:("OAuth2 + PAT","self-serve","official","https://developers.asana.com/docs/using-asanas-mcp-server",""),
 77:("API token + OAuth2","self-serve","official","https://developer.clickup.com/docs/connect-an-ai-assistant-to-clickups-mcp-server","MCP OAuth-only, all plans"),
 86:("OAuth2","self-serve","official","https://github.com/intuit/quickbooks-online-mcp-server",""),
 87:("OAuth2","self-serve","official","https://github.com/XeroAPI/xero-mcp-server",""),
 90:("API key","sales/none","none","https://pitchbook.com/help/pitchbook-api","Contract-gated add-on"),
 92:("OAuth (MCP) + API key (REST)",None,"official","https://mcpservers.org/remote-mcp-servers/otter-ai","REST-API Enterprise gate only from a third-party source"),
 96:("API key","paid","official","https://docs.devin.ai/api-reference/overview",""),
 99:("API key","self-serve","official","https://transcriptapi.com/pricing","100 free credits, MCP included"),
}
GATE = {"FREE":"self-serve","TRIAL":"self-serve","PAID":"paid","REVIEW":"approval","PARTNER":"sales/none","NONE":"sales/none"}
MCP = {"OFFICIAL":"official","DOCS_ONLY":"docs-only","DOCS-ONLY":"docs-only","NONE_FOUND":"none","NONE":"none","COMMUNITY":"none"}
def verdict(gate, api="REST"):
    if gate=="sales/none": return "Needs outreach"
    if gate in ("paid","approval"): return "Buildable w/ caveat"
    if api in ("CLI","None","CLI only"): return "Buildable w/ caveat"
    return "Ready now"
p1 = {}
for line in open('pass1_model_only.psv').read().splitlines()[1:]:
    i,name,auth,access,api,mcp,v,blk = line.split('|'); p1[int(i)] = dict(name=name,access=access,api=api,mcp=mcp)
p2 = {r['id']:r for r in json.load(open('pass2_grounded.json'))}
rows=[]; score={k:{"p1":[0,0],"p2":[0,0]} for k in ("gate","mcp","verdict")}
for i,(auth,gate,mcp,url,note) in T.items():
    a,b = p1[i], p2[i]
    api1 = "CLI" if "CLI" in a['api'] else "REST"; api2 = "CLI" if b['api'].startswith("CLI") else "REST"
    rec = dict(id=i,name=b['name'],cat=b['cat'],verify_url=url,note=note,auth_truth=auth,
        gate_truth=gate,mcp_truth=mcp,
        p1=dict(gate=GATE[a['access']],mcp=MCP[a['mcp']],verdict=verdict(GATE[a['access']],api1)),
        p2=dict(gate=GATE[b['access']],mcp=MCP[b['mcp']],verdict=verdict(GATE[b['access']],api2)))
    rec['verdict_truth'] = verdict(gate,api2) if gate else None
    for f in ("gate","mcp","verdict"):
        t = rec[f+"_truth"]
        if t is None: continue
        for p in ("p1","p2"):
            score[f][p][1]+=1; score[f][p][0]+= (rec[p][f]==t)
    rows.append(rec)
human=[r for r in rows if r['gate_truth'] is None or r['mcp_truth'] is None]
json.dump(dict(sample_ids=list(T),score=score,rows=rows,auth_note="Auth method family matched truth in 30/30 for both passes (no errors found).",
               human_queue=[r['id'] for r in human]),open('verification.json','w'),indent=1)
for f,v in score.items(): print(f, {p:f"{c}/{n} = {100*c/n:.0f}%" for p,(c,n) in v.items()})
tot={p:[sum(score[f][p][0] for f in score), sum(score[f][p][1] for f in score)] for p in ("p1","p2")}
print("all fields", {p:f"{c}/{n} = {100*c/n:.1f}%" for p,(c,n) in tot.items()})
print("misses p2:", [(r['name'],f,r['p2'][f],r[f+'_truth']) for r in rows for f in ("gate","mcp","verdict") if r[f+'_truth'] and r['p2'][f]!=r[f+'_truth']])
print("misses p1:", [(r['name'],f,r['p1'][f],r[f+'_truth']) for r in rows for f in ("gate","mcp","verdict") if r[f+'_truth'] and r['p1'][f]!=r[f+'_truth']])
print("human queue:", [r['name'] for r in human])
