"""Final dataset = pass 2 + fixes from verification loops, with per-row provenance and pass-1 diff."""
import json, collections, urllib.parse
R = json.load(open('pass2_grounded.json'))
V = json.load(open('verification.json'))
p1 = {}
for line in open('pass1_model_only.psv').read().splitlines()[1:]:
    i,name,auth,access,api,mcp,v,blk = line.split('|'); p1[int(i)] = dict(access=access,mcp={"COMMUNITY":"NONE_FOUND","NONE":"NONE_FOUND"}.get(mcp,mcp),verdict=v)
FIX = {  # id: (field, new, why, loop)
 29:[("access","TRIAL","Pricing: no free plan but free test access; API on every tier","L2 sample re-check")],
 30:[("mcp","DOCS_ONLY","Registry: io.github.Vonage/vonage-documentation-mcp is docs-only","L2 sample re-check")],
 34:[("mcp","OFFICIAL","HighLevel MCP (717 actions) at services.leadconnectorhq.com/mcp","L2 sample re-check"),("composio","Y","docs.composio.dev/toolkits/highlevel exists (listed as 'Highlevel')","L5 catalog check")],
 83:[("access","REVIEW","Account KYC (identity verification) before API keys; regional restrictions","L1 rule triage")],
 46:[("composio","Y","docs.composio.dev/toolkits/squarespace exists","L5 catalog check")],
 95:[("composio","Y","docs.composio.dev/toolkits/reducto exists","L5 catalog check")],
 40:[("access","TRIAL","Pricing: free plan retired, free trial only","L2 sample re-check")],
 42:[("mcp","OFFICIAL","WooCommerce MCP (developer preview, via MCP Adapter plugin)","L2 sample re-check")],
 4:[("mcp","OFFICIAL","docs.attio.com/mcp → mcp.attio.com/mcp (OAuth)","L3 negative re-check")],
 88:[("mcp","OFFICIAL","developer.brex.com nav lists 'Brex MCP'","L3 negative re-check")],
 5:[("mcp","OFFICIAL","twenty.com/pricing: MCP server included on all plans","L4 held-out check")],
 13:[("access","TRIAL","Free plan no longer listed; 14-day trial","L4 held-out check")],
 93:[("mcp","DOCS_ONLY","developers.fathom.ai/mcp is a read-only API-docs server","L3 negative re-check")],
}
EXTRA_EVID = {29:"https://aircall.io/pricing/",30:"https://registry.modelcontextprotocol.io/v0/servers?search=vonage",34:"https://marketplace.gohighlevel.com/docs/other/mcp/index.html",
 40:"https://www.twilio.com/en-us/sendgrid/pricing",42:"https://developer.woocommerce.com/docs/features/mcp/",4:"https://docs.attio.com/mcp/overview",88:"https://developer.brex.com/",93:"https://developers.fathom.ai/mcp",5:"https://twenty.com/pricing",13:"https://www.freshworks.com/freshdesk/pricing/"}
HUMAN = {6:"Is Podio's free plan still offered (pricing page blocks bots)?",10:"Does DealCloud's MCP server work for any customer site, and how is it authorised?",
 17:"Is Plain's MCP an action server or docs-only?",92:"Is Otter's REST API really Enterprise-only (only a third-party source says so)?",
 47:"Which Ecwid plan unlocks custom-app API tokens?",100:"Which Grain plan includes API tokens?",95:"Does Reducto self-serve signup include free credits?",
 50:"Confirm fanbasis has no partner/private API (contact vendor)."}
CONFIRMED_NONE = {11:"Zendesk developer docs: no MCP",32:"Meta Marketing API docs: no MCP"}
GATE={"FREE":"Self-serve (free)","TRIAL":"Self-serve (trial)","PAID":"Paid plan","REVIEW":"Approval / app review","PARTNER":"Sales / partner gate","NONE":"No public API"}
def verdict(r):
    if r['access']=="NONE": return "Not buildable today"
    if r['access']=="PARTNER": return "Needs outreach"
    if r['access'] in ("PAID","REVIEW") or r['api'].startswith("CLI") or "Enterprise" in r['api'] or "per-instance" in r['blocker'].lower() or "Per-store" in r['blocker'] or "Per-instance" in r['blocker']: return "Buildable w/ caveat"
    return "Ready now"
def main_blocker(r):
    a=r['access']
    if a=="NONE": return "No public API"
    if a=="PARTNER": return "Sales/partner or customer-only access"
    if a=="REVIEW": return "App review / approval tier"
    if a=="PAID": return "Paid plan required to test"
    if r['api'].startswith("CLI"): return "No API (local CLI)"
    if "Per-store" in r['blocker'] or "Per-instance" in r['blocker'] or "per-instance" in r['blocker']: return "Self-hosted / per-instance URL"
    return "—"
out=[]
for r in R:
    r=dict(r); r['changes']=[]
    for f,new,why,loop in FIX.get(r['id'],[]):
        r['changes'].append(dict(field=f,old=r[f],new=new,why=why,loop=loop)); r[f]=new
        if r['id'] in EXTRA_EVID: r['evidence'].append(EXTRA_EVID[r['id']])
        if f=="mcp": r['mcp_note']=why
        if f=="composio": continue
        if f=="access": r['access_note']=why
    r['gate']=GATE[r['access']]; r['verdict']=verdict(r); r['main_blocker']=main_blocker(r)
    r['human_question']=HUMAN.get(r['id']); r['status']="needs human check" if r['id'] in HUMAN else ("verified in sample" if r['id'] in V['sample_ids']+V.get('holdout',{}).get('ids',[]) else ("doc read" if r['grounding']=="read" else "canonical URL (not re-read)"))
    if r['id'] in CONFIRMED_NONE: r['mcp_note']=CONFIRMED_NONE[r['id']]
    r['pass1']=p1[r['id']]
    r['evidence']=list(dict.fromkeys(r['evidence']))
    out.append(r)
json.dump(out,open('final.json','w'),indent=1)
# ---------- patterns ----------
C=collections.Counter
auth=C(); 
for r in out:
    fam=set()
    for x in r['auth']:
        x=x.lower()
        if 'oauth2' in x: fam.add('OAuth2')
        elif 'oauth1' in x: fam.add('OAuth1')
        elif any(k in x for k in ('api key','token','pat','hmac','developer token','app key','service account','tenant','github app')): fam.add('API key / token')
        elif 'basic' in x: fam.add('Basic')
        elif 'jwt' in x: fam.add('JWT')
        elif 'none' in x: fam.add('None (CLI)')
        elif 'unknown' in x: fam.add('Unknown')
        else: fam.add(x)
    r['auth_family']=sorted(fam)
    for f in fam: auth[f]+=1
both=sum(1 for r in out if 'OAuth2' in r['auth_family'] and 'API key / token' in r['auth_family'])
oauth_only=sum(1 for r in out if r['auth_family']==['OAuth2'])
key_only=sum(1 for r in out if r['auth_family'] in (['API key / token'],['Basic'],['API key / token','Basic']))
cats=list(dict.fromkeys(r['cat'] for r in out))
matrix={c:C(r['gate'] for r in out if r['cat']==c) for c in cats}
vmat={c:C(r['verdict'] for r in out if r['cat']==c) for c in cats}
blk=C(r['main_blocker'] for r in out if r['main_blocker']!="—")
mcp=C(r['mcp'] for r in out)
diff=sum(1 for r in out for f in ('access','mcp') if r['pass1'][f]!=r[f])
easy=[r['name'] for r in out if r['verdict']=="Ready now" and r['composio']=="N"]
easy_mcp=[r['name'] for r in out if r['verdict']=="Ready now" and r['mcp']=="OFFICIAL"]
P=dict(auth=auth,both=both,oauth_only=oauth_only,key_only=key_only,gate=C(r['gate'] for r in out),verdict=C(r['verdict'] for r in out),
  blockers=blk,mcp=mcp,matrix=matrix,vmatrix=vmat,cats=cats,pass1_vs_final_field_diffs=diff,
  not_in_composio_ready=easy,composio=C(r['composio'] for r in out),
  outreach=[r['name'] for r in out if r['verdict'] in ("Needs outreach","Not buildable today")],
  status=C(r['status'] for r in out))
json.dump(out,open('final.json','w'),indent=1); json.dump(P,open('patterns.json','w'),indent=1)
for k,v in P.items(): print(k,':',v)
