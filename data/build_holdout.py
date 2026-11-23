"""L4: held-out sample (seed 7, 1 per category, excluding every row touched by L2/L3 or the human queue).
Truth recorded from a page different from the pass-2 evidence; scored against FINAL data and pass 1."""
import json
H = {5:("self-serve","official","Ready now","https://twenty.com/pricing","Pricing: 'MCP server included on all plans' → our 'no MCP' was wrong"),
 13:("self-serve","none","Ready now","https://www.freshworks.com/freshdesk/pricing/","No free plan any more: 14-day trial (gate class unchanged)"),
 24:(None,"official",None,"https://github.com/larksuite/lark-openapi-mcp","Console pricing not stated → gate excluded"),
 39:("approval","none","Buildable w/ caveat","https://developers.facebook.com/docs/threads/get-started",""),
 43:("self-serve","docs-only","Ready now","https://docs.bigcommerce.com/developer/docs/overview/sandboxes",""),
 51:("self-serve","official","Ready now","https://dataforseo.com/model-context-protocol",""),
 70:(None,"official",None,"https://mcp.sentry.dev/","Plan not on page → gate excluded"),
 78:("self-serve",None,"Ready now","https://coda.io/developers/apis/v1","coda.io/developers blocks bots → MCP excluded"),
 81:("self-serve","official","Ready now","https://docs.stripe.com/mcp",""),
 97:("paid","official","Buildable w/ caveat","https://higgsfield.ai/pricing","")}
# 'final' = the dataset as it stood when the held-out check ran (before the L4 fixes to Twenty/Freshdesk)
AT_CHECK = {5:dict(mcp="none")}
F={r['id']:r for r in json.load(open('final.json'))}
GATE={"Self-serve (free)":"self-serve","Self-serve (trial)":"self-serve","Paid plan":"paid","Approval / app review":"approval","Sales / partner gate":"sales/none","No public API":"sales/none"}
G1={"FREE":"self-serve","TRIAL":"self-serve","PAID":"paid","REVIEW":"approval","PARTNER":"sales/none","NONE":"sales/none"}
MCP={"OFFICIAL":"official","DOCS_ONLY":"docs-only","NONE_FOUND":"none"}
def v1(g): return {"sales/none":"Needs outreach","paid":"Buildable w/ caveat","approval":"Buildable w/ caveat"}.get(g,"Ready now")
rows=[];sc={"final":[0,0],"p1":[0,0]}
for i,(g,m,v,url,note) in H.items():
    r=F[i]; fin=dict(gate=GATE[r['gate']],mcp=MCP[r['mcp']],verdict=r['verdict']); fin.update(AT_CHECK.get(i,{}))
    p=dict(gate=G1[r['pass1']['access']],mcp=MCP.get(r['pass1']['mcp'],'none'),verdict=v1(G1[r['pass1']['access']]))
    for f,t in (("gate",g),("mcp",m),("verdict",v)):
        if t is None: continue
        sc['final'][1]+=1; sc['final'][0]+=fin[f]==t; sc['p1'][1]+=1; sc['p1'][0]+=p[f]==t
    rows.append(dict(id=i,name=r['name'],cat=r['cat'],gate_truth=g,mcp_truth=m,verdict_truth=v,final=fin,p1=p,verify_url=url,note=note))
V=json.load(open('verification.json')); V['holdout']=dict(ids=list(H),rows=rows,score=sc); json.dump(V,open('verification.json','w'),indent=1)
print("held-out:",sc)
