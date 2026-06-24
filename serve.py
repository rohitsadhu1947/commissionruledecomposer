"""
Tiny zero-dependency web UI to test the commission engine in a browser.

Run:  python3 serve.py     then open  http://localhost:8000

Endpoints:
  GET  /         -> HTML test console
  GET  /meta     -> dropdown options (states, sub-segments, ...)
  GET  /rules    -> all extracted rate + eligibility rules + warnings
  POST /quote    -> {risk} -> ALLOW/DECLINE/NO_RATE with trace
"""
import json
import os
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from poc_tw_extractor import extract
from resolution_engine import quote, check_eligibility, resolve_rate
from geo_normalize import to_state

RATE_RULES, WARNINGS = extract()
with open("poc_tw_notes_rules.json") as f:
    ELIG_RULES = json.load(f)["eligibility_rules"]
MOD_RULES = []

# canonical states (folded through the RTO master) that appear in any rate/elig rule
_raw = ({r["scope"]["state"] for r in RATE_RULES} |
        {s for e in ELIG_RULES for s in e["scope"].get("states", [])} |
        {s for e in ELIG_RULES for s in e["effect"].get("allowed_states", [])})
STATES = sorted({to_state(s) or s for s in _raw})

# ---- rule-review workflow: the atomic catalog + persisted sign-off decisions ----
CATALOG_FILE = "rules_catalog.json"
REVIEW_FILE = "rules_review.json"


def load_catalog():
    if not os.path.exists(CATALOG_FILE):
        return {"meta": {}, "rules": []}
    with open(CATALOG_FILE) as f:
        return json.load(f)


def load_review():
    if not os.path.exists(REVIEW_FILE):
        return {}
    with open(REVIEW_FILE) as f:
        return json.load(f)


def save_review(state):
    tmp = REVIEW_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, REVIEW_FILE)

PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>Commission Engine — Test Console</title>
<style>
 body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
 header{padding:14px 20px;background:#171a21;border-bottom:1px solid #2a2f3a}
 header b{color:#6cf}
 .wrap{display:flex;gap:20px;padding:20px;flex-wrap:wrap}
 .card{background:#171a21;border:1px solid #2a2f3a;border-radius:10px;padding:18px;min-width:320px}
 label{display:block;margin:8px 0 2px;color:#9aa4b2;font-size:12px}
 input,select{width:100%;padding:8px;background:#0f1115;border:1px solid #2a2f3a;color:#e6e6e6;border-radius:6px;box-sizing:border-box}
 button{margin-top:14px;padding:10px 16px;background:#2563eb;color:#fff;border:0;border-radius:6px;cursor:pointer;font-weight:600}
 button:hover{background:#1d4ed8}
 .res{margin-top:16px;padding:14px;border-radius:8px;font-size:15px}
 .ALLOW{background:#0f2e1a;border:1px solid #1d7a45}
 .DECLINE{background:#2e1316;border:1px solid #a13b45}
 .NO_RATE{background:#2e2913;border:1px solid #a18a3b}
 .big{font-size:28px;font-weight:700}
 table{border-collapse:collapse;width:100%;font-size:12px}
 th,td{border-bottom:1px solid #2a2f3a;padding:5px 8px;text-align:left}
 th{color:#9aa4b2;position:sticky;top:0;background:#171a21}
 .tabs button{background:#0f1115;border:1px solid #2a2f3a;margin:0 4px 0 0;padding:6px 12px}
 .tabs button.on{background:#2563eb}
 .scroll{max-height:420px;overflow:auto;margin-top:10px}
 small{color:#9aa4b2}
 .status{padding:6px 20px;font-size:12px;background:#0c1320;border-bottom:1px solid #2a2f3a}
 .err{background:#2e1316;border:1px solid #a13b45;color:#ffd2d2;padding:10px;border-radius:6px;margin-top:10px}
 .rbar{display:flex;align-items:center;gap:10px;margin:4px 0 8px;flex-wrap:wrap}
 .rbar select,.rbar input{width:auto;padding:5px 8px}
 .prog{flex:1;height:8px;background:#0f1115;border:1px solid #2a2f3a;border-radius:6px;overflow:hidden;min-width:120px}
 .prog>i{display:block;height:100%;background:#1d7a45}
 .badge{font-size:10px;padding:2px 6px;border-radius:4px;font-weight:700;white-space:nowrap}
 .b-PENDING{background:#3a3320;color:#e7c84b}
 .b-CONFIRMED{background:#0f2e1a;color:#5fd08a}
 .b-REJECTED{background:#2e1316;color:#ff8a8a}
 .rtbl td input{padding:3px 5px;font-size:11px}
 .rtbl .ok{background:#1d7a45;padding:4px 8px;margin:0 2px 0 0}
 .rtbl .no{background:#a13b45;padding:4px 8px;margin:0}
 .rtbl button{margin-top:0;font-size:11px}
</style></head><body>
<header><b>Commission Engine</b> &mdash; SBI General &middot; Two-Wheeler POC &middot; <small>rates + notes/eligibility enforced</small></header>
<div class=status id=status>connecting&hellip;</div>
<div class=wrap>
 <div class=card style="flex:0 0 340px">
  <h3>Get Pay-in</h3>
  <label>Category</label><select id=category><option>TW</option></select>
  <label>Sub-segment</label><select id=sub_segment><option>SCOOTER</option><option>BIKE</option></select>
  <label>Policy type</label><select id=policy_type><option>COMP</option><option>SAOD</option><option>SATP</option></select>
  <label>State</label><select id=state><option>HIMACHAL PRADESH</option></select>
  <label>RTO code (optional, e.g. TN33)</label><input id=rto_code placeholder="blank = use state">
  <label>CC</label><input id=cc type=number value=110>
  <label>Make</label><input id=make value="Honda">
  <label>Model</label><input id=model value="Activa">
  <label>Vehicle age (years)</label><input id=age_years type=number value=3>
  <button id=calc type=button>Calculate</button>
  <div id=out></div>
 </div>
 <div class=card style="flex:1 1 480px">
  <div class=tabs>
   <button type=button class=on data-tab=rate>Rate rules</button>
   <button type=button data-tab=elig>Eligibility rules</button>
   <button type=button data-tab=warn>Warnings</button>
   <button type=button data-tab=review>Review catalog</button>
  </div>
  <div id=panel class=scroll></div>
 </div>
</div>
<script>
var META={states:[]}, RULES={rate:[],elig:[],warn:[]};
var CAT={meta:{},rules:[],review:{}}, RFILTER='ALL';
function $(id){return document.getElementById(id);}
function val(id){return $(id).value;}
function setStatus(t,isErr){var s=$('status');s.textContent=t;s.style.color=isErr?'#ff8a8a':'#9aa4b2';}
function band(b){return b.min_cc+'-'+(b.max_cc==null?'+':b.max_cc);}
function esc(x){return (x==null?'':String(x)).replace(/</g,'&lt;');}
function tbl(h,rows){
 var html='<table><tr>'+h.map(function(x){return '<th>'+esc(x)+'</th>';}).join('')+'</tr>';
 html+=rows.map(function(r){return '<tr>'+r.map(function(c){return '<td>'+esc(c)+'</td>';}).join('')+'</tr>';}).join('');
 return html+'</table>';
}
function show(which){
 var btns=document.querySelectorAll('.tabs button');
 for(var i=0;i<btns.length;i++) btns[i].classList.toggle('on', btns[i].getAttribute('data-tab')===which);
 var p=$('panel');
 if(which==='rate'){
  p.innerHTML=tbl(['Rule','Sub','CC band','Policy','State','%','Cell'],
   RULES.rate.map(function(r){return [r.rule_id,r.scope.sub_segment,band(r.scope.cc_band),
    r.scope.policy_type.join('/'),r.scope.state,r.effect.value,r.source.cell];}));
 }else if(which==='elig'){
  p.innerHTML=tbl(['Rule','Effect','Reason'],
   RULES.elig.map(function(r){return [r.rule_id, r.effect.mode||('allowed:'+r.effect.allowed), r.effect.reason||''];}));
 }else if(which==='warn'){
  p.innerHTML=tbl(['Where','Issue'],RULES.warn.map(function(w){return [w.cell||w.scope||'',w.issue];}));
 }else if(which==='review'){
  renderReview();
 }
}
function rStatus(cid){var r=CAT.review[cid];return r&&r.status?r.status:'PENDING';}
function rPct(rule){var r=CAT.review[rule.catalog_id];return (r&&r.pay_in_pct!=null)?r.pay_in_pct:rule.pay_in_pct;}
function renderReview(){
 var p=$('panel');
 var rules=CAT.rules;
 var total=rules.length, done=0;
 for(var i=0;i<rules.length;i++){var s=rStatus(rules[i].catalog_id);if(s==='CONFIRMED'||s==='REJECTED')done++;}
 var pct=total?Math.round(done*100/total):0;
 var view=rules.filter(function(r){
   var s=rStatus(r.catalog_id);
   if(RFILTER==='ALL')return true;
   if(RFILTER==='RATE')return r.rule_type==='RATE';
   if(RFILTER==='ELIGIBILITY')return r.rule_type==='ELIGIBILITY';
   return s===RFILTER;
 });
 var html='<div class=rbar>'+
  '<b>'+done+' / '+total+' reviewed</b>'+
  '<div class=prog><i style="width:'+pct+'%"></i></div>'+
  '<select id=rfilter>'+
   ['ALL','PENDING','CONFIRMED','REJECTED','RATE','ELIGIBILITY'].map(function(f){
     return '<option'+(f===RFILTER?' selected':'')+'>'+f+'</option>';}).join('')+
  '</select>'+
  '<button type=button id=rexport style="margin:0;padding:6px 12px">Export approved</button>'+
  '<small>showing '+view.length+'</small>'+
  '<small id=rdl style="flex-basis:100%"></small></div>';
 var rows=view.slice(0,400).map(function(r){
   var s=rStatus(r.catalog_id);
   var isRate=r.rule_type==='RATE';
   var pctIn=isRate?('<input id="pct_'+r.catalog_id+'" style="width:54px" value="'+esc(rPct(r))+'">'):'';
   var reasonIn='<input id="rsn_'+r.catalog_id+'" value="'+esc((CAT.review[r.catalog_id]&&CAT.review[r.catalog_id].reason)||r.reason||'')+'">';
   return '<tr>'+
     '<td><span class="badge b-'+s+'">'+s+'</span></td>'+
     '<td>'+esc(r.catalog_id)+'</td>'+
     '<td>'+esc(r.effect)+'</td>'+
     '<td>'+esc(r.sub_segment)+' '+esc(r.policy_type)+'</td>'+
     '<td>'+esc(r.make)+' '+esc(r.model)+'</td>'+
     '<td>'+esc(r.geo_label)+'</td>'+
     '<td>'+pctIn+'</td>'+
     '<td>'+reasonIn+'</td>'+
     '<td style="white-space:nowrap">'+
       '<button type=button class=ok data-act=CONFIRMED data-id="'+esc(r.catalog_id)+'">✓</button>'+
       '<button type=button class=no data-act=REJECTED data-id="'+esc(r.catalog_id)+'">✗</button>'+
     '</td></tr>';
 }).join('');
 html+='<table class=rtbl><tr>'+
   ['Status','Catalog ID','Effect','Segment','Make/Model','Geo','%','Reason',''].map(function(h){return '<th>'+h+'</th>';}).join('')+
   '</tr>'+rows+'</table>';
 if(view.length>400)html+='<small>… showing first 400 of '+view.length+'. Use a filter to narrow.</small>';
 p.innerHTML=html;
 $('rfilter').addEventListener('change',function(){RFILTER=this.value;renderReview();});
 $('rexport').addEventListener('click',function(){
   setStatus('exporting approved catalog…',false);
   fetch('/export',{method:'POST'}).then(function(r){return r.json();})
   .then(function(res){
     if(res.ok){var s=res.summary;
       setStatus('exported · '+s.confirmed+' confirmed, '+s.rejected+' dropped, '+s.pending+' pending → '+s.exported+' rows',false);
       var dl=$('rdl'); if(dl){
         dl.innerHTML='Download: '+res.files.map(function(f){
           return '<a href="/download/'+f+'" download style="color:#6cf;margin:0 8px">'+f.split('.').pop().toUpperCase()+'</a>';
         }).join('');
       }
       // auto-trigger the CSV download so the file lands in the browser
       var a=document.createElement('a');
       a.href='/download/rules_catalog_approved.csv'; a.download='rules_catalog_approved.csv';
       document.body.appendChild(a); a.click(); document.body.removeChild(a);
     }
     else setStatus('export failed',true);
   }).catch(function(e){setStatus('export error: '+e,true);});
 });
 var bs=p.querySelectorAll('.rtbl button');
 for(var i=0;i<bs.length;i++){(function(b){b.addEventListener('click',function(){
   saveReview(b.getAttribute('data-id'),b.getAttribute('data-act'));});})(bs[i]);}
}
function saveReview(cid,status){
 var body={catalog_id:cid,status:status,reviewer:'console'};
 var pe=$('pct_'+cid); if(pe&&pe.value!=='')body.pay_in_pct=+pe.value;
 var re=$('rsn_'+cid); if(re)body.reason=re.value;
 fetch('/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 .then(function(r){return r.json();})
 .then(function(res){
   if(res.ok){CAT.review[cid]=res.entry;renderReview();
     setStatus('saved '+cid+' = '+status+' · '+res.reviewed+' reviewed',false);}
   else setStatus('save failed: '+(res.error||'?'),true);
 })
 .catch(function(e){setStatus('save error: '+e,true);});
}
function boot(){
 Promise.all([fetch('/meta').then(function(r){return r.json();}),
              fetch('/rules').then(function(r){return r.json();}),
              fetch('/catalog').then(function(r){return r.json();})])
 .then(function(res){
   META=res[0]; RULES=res[1]; CAT=res[2];
   var s=$('state');
   s.innerHTML=META.states.map(function(x){return '<option>'+esc(x)+'</option>';}).join('');
   s.value = META.states.indexOf('HIMACHAL PRADESH')>=0?'HIMACHAL PRADESH':META.states[0];
   show('rate');
   setStatus('connected · '+RULES.rate.length+' rate rules, '+RULES.elig.length+' eligibility rules · '+CAT.rules.length+' catalog rules to review',false);
 })
 .catch(function(e){ setStatus('failed to load rules: '+e+' (is serve.py running?)',true); });
}
function runQuote(){
 setStatus('calculating…',false);
 var risk={category:val('category'),sub_segment:val('sub_segment'),policy_type:val('policy_type'),
  state:val('state'),rto_code:val('rto_code')||null,cc:+val('cc'),make:val('make'),model:val('model'),
  age_years:+val('age_years')};
 fetch('/quote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(risk)})
 .then(function(resp){ if(!resp.ok) throw new Error('HTTP '+resp.status); return resp.json(); })
 .then(function(r){
   var html='<div class="res '+r.decision+'">';
   if(r.decision==='ALLOW'){
     html+='<div class=big>'+r.pay_in_pct+'% <small>on '+r.applies_on+'</small></div>'+
       '<small>base '+r.base_pct+'% · rate rule '+r.rate_rule+
       (r.modifiers&&r.modifiers.length?' · modifiers '+esc(JSON.stringify(r.modifiers)):'')+'</small>';
   }else if(r.decision==='DECLINE'){
     html+='<div class=big>DECLINED</div>'+
       r.reasons.map(function(x){return '<div>• '+esc(x[1])+' <small>('+esc(x[0])+')</small></div>';}).join('');
   }else{
     html+='<div class=big>No rate</div><small>'+esc(r.reason||'')+'</small>';
   }
   $('out').innerHTML=html+'</div>';
   setStatus('done · '+r.decision,false);
 })
 .catch(function(e){ $('out').innerHTML='<div class=err>Request failed: '+esc(e)+'</div>'; setStatus('error',true); });
}
document.addEventListener('DOMContentLoaded',function(){
 $('calc').addEventListener('click',runQuote);
 var btns=document.querySelectorAll('.tabs button');
 for(var i=0;i<btns.length;i++){
   (function(b){ b.addEventListener('click',function(){show(b.getAttribute('data-tab'));}); })(btns[i]);
 }
 boot();
});
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *a):
        print("  %s - %s" % (self.address_string(), fmt % a))

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif self.path == "/meta":
            self._send(200, json.dumps({"states": STATES}))
        elif self.path == "/rules":
            self._send(200, json.dumps({"rate": RATE_RULES, "elig": ELIG_RULES, "warn": WARNINGS}))
        elif self.path == "/catalog":
            cat = load_catalog()
            self._send(200, json.dumps({"meta": cat.get("meta", {}),
                                        "rules": cat.get("rules", []),
                                        "review": load_review()}))
        elif self.path.startswith("/download/"):
            self._download(self.path[len("/download/"):])
        else:
            self._send(404, "{}")

    # only these generated artifacts may be downloaded
    DOWNLOADABLE = {
        "rules_catalog.xlsx", "rules_catalog.csv", "rules_catalog.json",
        "rules_catalog_approved.xlsx", "rules_catalog_approved.csv", "rules_catalog_approved.json",
    }
    CTYPES = {".csv": "text/csv", ".json": "application/json",
              ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}

    def _download(self, name):
        name = os.path.basename(name)  # prevent path traversal
        if name not in self.DOWNLOADABLE or not os.path.exists(name):
            return self._send(404, json.dumps({"error": "not found: " + name}))
        with open(name, "rb") as f:
            data = f.read()
        ext = os.path.splitext(name)[1]
        self.send_response(200)
        self.send_header("Content-Type", self.CTYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % name)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or "{}") if n else {}
        if self.path == "/quote":
            return self._send(200, json.dumps(quote(RATE_RULES, ELIG_RULES, MOD_RULES, body)))
        if self.path == "/review":
            # body: {catalog_id, status: CONFIRMED|REJECTED|PENDING, pay_in_pct?, reason?}
            cid = body.get("catalog_id")
            if not cid:
                return self._send(400, json.dumps({"error": "catalog_id required"}))
            state = load_review()
            entry = {"status": body.get("status", "PENDING"),
                     "reviewer": body.get("reviewer", "unknown"),
                     "ts": datetime.datetime.now().isoformat(timespec="seconds")}
            for k in ("pay_in_pct", "reason"):
                if body.get(k) not in (None, ""):
                    entry[k] = body[k]
            state[cid] = entry
            save_review(state)
            done = sum(1 for v in state.values() if v.get("status") in ("CONFIRMED", "REJECTED"))
            return self._send(200, json.dumps({"ok": True, "entry": entry, "reviewed": done}))
        if self.path == "/export":
            import export_approved
            summary = export_approved.main()
            return self._send(200, json.dumps({"ok": True, "summary": summary,
                                                "files": ["rules_catalog_approved.xlsx",
                                                          "rules_catalog_approved.csv",
                                                          "rules_catalog_approved.json"]}))
        return self._send(404, "{}")


if __name__ == "__main__":
    print("Commission test console -> http://localhost:8000  (Ctrl+C to stop)")
    print(f"Loaded {len(RATE_RULES)} rate rules, {len(ELIG_RULES)} eligibility rules, {len(WARNINGS)} warnings")
    ThreadingHTTPServer(("127.0.0.1", 8000), H).serve_forever()
