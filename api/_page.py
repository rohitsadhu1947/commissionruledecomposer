# HTML test console for the serverless deployment. Adapted from serve.py:
# export uses GET /export/approved.<fmt> + /export/summary (review state is in KV),
# and a reviewer name is captured once (localStorage) for shared attribution.
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
<header><b>Commission Engine</b> &mdash; Motor pay-in <small id=hdr-ins>multi-insurer &mdash; rates + eligibility enforced</small></header>
<div class=status id=status>connecting&hellip;</div>
<div class=wrap>
 <div class=card style="flex:0 0 360px">
  <h3>Resolve Pay-in <small>(live catalog)</small></h3>
  <label>Insurer</label><select id=insurer></select>
  <label>Category</label><select id=category></select>
  <label>Sub-segment</label><select id=sub_segment></select>
  <label>Policy type</label><select id=policy_type></select>
  <label>Make / tier (optional)</label><input id=make list=makelist placeholder="(any)"><datalist id=makelist></datalist>
  <label>Model (optional)</label><input id=model placeholder="(any)">
  <label>RTO code (optional)</label><input id=rto_code placeholder="e.g. MH01 — pins the cluster">
  <label>RTO cluster (optional)</label><input id=cluster list=geolist placeholder="e.g. MH - M / AP - Rest"><datalist id=geolist></datalist>
  <label>State (optional)</label><select id=state><option value="">(any)</option></select>
  <label>CC (optional)</label><input id=cc type=number placeholder="e.g. 1200">
  <label>Vehicle age years (optional)</label><input id=age_years type=number placeholder="0 = new">
  <button id=calc type=button>Resolve</button>
  <div id=out></div>
 </div>
 <div class=card style="flex:1 1 480px">
  <div class=tabs>
   <button type=button class=on data-tab=rate>Rate rules</button>
   <button type=button data-tab=elig>Eligibility rules</button>
   <button type=button data-tab=warn>Warnings</button>
   <button type=button data-tab=review>Review catalog</button>
   <button type=button data-tab=upload>Upload grid</button>
  </div>
  <div id=panel class=scroll></div>
 </div>
</div>
<script>
var META={states:[]}, RULES={rate:[],elig:[],warn:[]};
var CAT={meta:{},rules:[],review:{}}, OPT={};
function $(id){return document.getElementById(id);}
function val(id){return $(id).value;}
function setStatus(t,isErr){var s=$('status');s.textContent=t;s.style.color=isErr?'#ff8a8a':'#9aa4b2';}
function band(b){return b.min_cc+'-'+(b.max_cc==null?'+':b.max_cc);}
function esc(x){return (x==null?'':String(x)).replace(/</g,'&lt;');}
function reviewer(){var n=localStorage.getItem('reviewer'); if(!n){n=prompt('Your name (for review attribution):')||'anon'; localStorage.setItem('reviewer',n);} return n;}
function fillSel(id,arr,blank){var s=$(id);s.innerHTML=(blank?'<option value="">(any)</option>':'')+arr.map(function(x){return '<option>'+esc(x)+'</option>';}).join('');}
function fillList(id,arr){$(id).innerHTML=arr.map(function(x){return '<option value="'+esc(x)+'">';}).join('');}
function insOpt(){return OPT[val('insurer')]||{};}
function onIns(){
 var order=['PVT_CAR','GCV','PCV','MISD','TW'];
 var cats=Object.keys(insOpt()).sort(function(a,b){return (order.indexOf(a)+1||9)-(order.indexOf(b)+1||9);});
 fillSel('category',cats,false);onCat();
 if(CAT.rules&&CAT.rules.length)show(CURTAB);
}
function onCat(){var c=insOpt()[val('category')]||{subs:{},geo:[]};fillSel('sub_segment',Object.keys(c.subs).sort(),false);fillList('geolist',c.geo||[]);onSub();}
function onSub(){var c=insOpt()[val('category')]||{subs:{}};var s=c.subs[val('sub_segment')]||{policy:[],make:[]};fillSel('policy_type',s.policy||[],true);fillList('makelist',s.make||[]);}
function candTable(c,n){return '<div style="margin-top:10px"><small>top candidates (of '+n+'):</small><table><tr><th>%</th><th>Policy</th><th>Make/tier</th><th>Geo</th><th>cc</th><th>age</th><th>Cell</th></tr>'+
 c.map(function(x){return '<tr><td><b>'+esc(x.pay_in_pct)+'</b></td><td>'+esc(x.policy_type)+'</td><td>'+esc(x.make)+'</td><td>'+esc(x.geo_label)+'</td><td>'+esc(x.cc_min)+'-'+esc(x.cc_max||'+')+'</td><td>'+esc(x.age_min)+'-'+esc(x.age_max||'+')+'</td><td><small>'+esc(x.source_sheet)+'!'+esc(x.source_cell)+'</small></td></tr>';}).join('')+'</table></div>';}
function tbl(h,rows){
 var html='<table><tr>'+h.map(function(x){return '<th>'+esc(x)+'</th>';}).join('')+'</tr>';
 html+=rows.map(function(r){return '<tr>'+r.map(function(c){return '<td>'+esc(c)+'</td>';}).join('')+'</tr>';}).join('');
 return html+'</table>';
}
var CURTAB='rate';
// Per-tab filter state. Every tab is ALSO scoped to the insurer selected on the left.
var FILT={
 rate:{cat:'',sub:'',pol:'',geo:'',q:''},
 elig:{cat:'',sub:'',pol:'',geo:'',q:''},
 warn:{q:''},
 review:{status:'',type:'',cat:'',sub:'',pol:'',geo:'',q:''}
};
function bandTxt(lo,hi){return (lo===''&&hi==='')?'':(lo===''?'0':lo)+'-'+(hi===''||hi==null?'+':hi);}
function uniq(rows,key){var s={};rows.forEach(function(r){if(r[key])s[r[key]]=1;});return Object.keys(s).sort();}
function applyFilt(rows,f){
 return rows.filter(function(r){
  if(f.status&&rStatus(r.catalog_id)!==f.status)return false;
  if(f.type&&r.rule_type!==f.type)return false;
  if(f.cat&&r.category!==f.cat)return false;
  if(f.sub&&r.sub_segment!==f.sub)return false;
  if(f.pol&&r.policy_type!==f.pol)return false;
  if(f.geo&&String(r.geo_label).toLowerCase().indexOf(f.geo.toLowerCase())<0)return false;
  if(f.q){var hay=(r.catalog_id+' '+r.sub_segment+' '+(r.make||'')+' '+(r.model||'')+' '+(r.geo_label||'')+' '+(r.policy_type||'')+' '+(r.reason||'')+' '+(r.source_text||'')).toLowerCase();
   if(hay.indexOf(f.q.toLowerCase())<0)return false;}
  return true;
 });
}
function selHTML(id,opts,cur,label){return '<select id="'+id+'" style="width:auto;padding:5px 8px"><option value="">'+label+'</option>'+
 opts.map(function(o){return '<option'+(o===cur?' selected':'')+'>'+esc(o)+'</option>';}).join('')+'</select>';}
function filtBar(tab,base){
 var f=FILT[tab];
 var h='';
 if(tab==='review'){
  h+=selHTML(tab+'_status',['PENDING','CONFIRMED','REJECTED'],f.status,'status: all')+
     selHTML(tab+'_type',['RATE','ELIGIBILITY'],f.type,'type: all');
 }
 h+=selHTML(tab+'_cat',uniq(base,'category'),f.cat,'category: all')+
  selHTML(tab+'_sub',uniq(base.filter(function(r){return !f.cat||r.category===f.cat;}),'sub_segment'),f.sub,'sub-segment: all')+
  selHTML(tab+'_pol',uniq(base.filter(function(r){return (!f.cat||r.category===f.cat)&&(!f.sub||r.sub_segment===f.sub);}),'policy_type'),f.pol,'policy: all')+
  '<input id="'+tab+'_geo" placeholder="geo contains…" value="'+esc(f.geo)+'" style="width:110px;padding:5px 8px">'+
  '<input id="'+tab+'_q" placeholder="search…" value="'+esc(f.q)+'" style="width:130px;padding:5px 8px">'+
  '<button type=button id="'+tab+'_clr" style="margin:0;padding:5px 10px">clear</button>';
 return h;
}
function rerender(){
 var ae=document.activeElement,id=ae?ae.id:null;
 var pos=(ae&&ae.selectionStart!=null)?ae.selectionStart:null;
 show(CURTAB);
 if(id){var e=$(id);if(e){e.focus();if(pos!=null&&e.setSelectionRange){try{e.setSelectionRange(pos,pos);}catch(_){}}}}
}
function bindFilt(tab){
 var f=FILT[tab];
 [['_status','status'],['_type','type'],['_cat','cat'],['_sub','sub'],['_pol','pol']].forEach(function(pair){
  var e=$(tab+pair[0]);if(!e)return;
  e.addEventListener('change',function(){
    f[pair[1]]=this.value;
    if(pair[1]==='cat'){f.sub='';f.pol='';}
    if(pair[1]==='sub'){f.pol='';}
    rerender();});
 });
 [['_geo','geo'],['_q','q']].forEach(function(pair){
  var e=$(tab+pair[0]);if(!e)return;
  e.addEventListener('input',function(){f[pair[1]]=this.value;clearTimeout(e._t);e._t=setTimeout(rerender,300);});
 });
 var c=$(tab+'_clr');if(c)c.addEventListener('click',function(){
   Object.keys(f).forEach(function(k){f[k]='';});rerender();});
}
function show(which){
 CURTAB=which;
 var btns=document.querySelectorAll('.tabs button');
 for(var i=0;i<btns.length;i++) btns[i].classList.toggle('on', btns[i].getAttribute('data-tab')===which);
 var p=$('panel');
 var ins=val('insurer');
 if(which==='rate'||which==='elig'){
  var base=CAT.rules.filter(function(r){return r.rule_type===(which==='rate'?'RATE':'ELIGIBILITY')&&(!ins||r.insurer===ins);});
  var rows=applyFilt(base,FILT[which]);
  var head='<small>'+rows.length+' of '+base.length+' '+(which==='rate'?'rate':'eligibility')+' rules · '+esc(ins||'all insurers')+(rows.length>500?' · showing first 500':'')+'</small>';
  if(which==='rate'){
   p.innerHTML='<div class=rbar>'+filtBar('rate',base)+'</div>'+head+
    tbl(['Catalog ID','Cat','Sub-segment','Make','Policy','cc','age','Geo','%','Cell'],
    rows.slice(0,500).map(function(r){return [r.catalog_id,r.category,r.sub_segment,r.make,r.policy_type,
     bandTxt(r.cc_min,r.cc_max),bandTxt(r.age_min,r.age_max),r.geo_label,r.pay_in_pct,r.source_cell];}));
  }else{
   p.innerHTML='<div class=rbar>'+filtBar('elig',base)+'</div>'+head+
    tbl(['Catalog ID','Effect','Cat','Sub','Make/Model','Policy','Geo','Reason'],
    rows.slice(0,500).map(function(r){return [r.catalog_id,r.effect,r.category,r.sub_segment,
     (r.make||'')+' '+(r.model||''),r.policy_type,r.geo_label,r.reason];}));
  }
  bindFilt(which);
 }else if(which==='warn'){
  var f=FILT.warn;
  var base=((CAT.meta&&CAT.meta.warnings)||[]).filter(function(w){return !ins||!w.insurer||w.insurer===ins;});
  var ws=base.filter(function(w){
    if(!f.q)return true;
    var hay=((w.insurer||'')+' '+(w.cell||'')+' '+(w.scope||'')+' '+(w.issue||'')).toLowerCase();
    return hay.indexOf(f.q.toLowerCase())>=0;});
  p.innerHTML='<div class=rbar>'+
    '<input id=warn_q placeholder="search…" value="'+esc(f.q)+'" style="width:200px;padding:5px 8px">'+
    '<button type=button id=warn_clr style="margin:0;padding:5px 10px">clear</button>'+
    '<small>'+ws.length+' of '+base.length+' warnings · '+esc(ins||'all insurers')+'</small></div>'+
   tbl(['Insurer','Where','Issue'],ws.map(function(w){return [w.insurer||'',w.cell||w.scope||'',w.issue];}));
  bindFilt('warn');
 }else if(which==='review'){
  renderReview();
 }else if(which==='upload'){
  p.innerHTML='<small>loading version state…</small>';
  fetch('/versions').then(function(r){return r.json();}).then(renderUpload)
   .catch(function(e){p.innerHTML='<div class=err>'+esc(e)+'</div>';});
 }
}
var UPB64='', UPNAME='';
function fileB64(f,cb){var rd=new FileReader();rd.onload=function(){cb(String(rd.result).split(',')[1]||'');};rd.readAsDataURL(f);}
function reloadData(){
 Promise.all([fetch('/catalog').then(function(r){return r.json();}),
              fetch('/options').then(function(r){return r.json();})])
 .then(function(res){CAT=res[0];OPT=res[1];onIns();
   setStatus('catalog reloaded · '+CAT.rules.length+' rules',false);});
}
function renderUpload(v){
 var p=$('panel');
 var inss=Object.keys(v.insurers);
 var html='<div class=rbar><b>Monthly grid upload</b> <small>'+
  (v.persisted?'storage connected · uploads persist':'⚠ KV NOT configured — commits will NOT survive; connect Upstash/Redis to the Vercel project')+'</small></div>';
 html+='<table><tr><th>Insurer</th><th>Baked rows</th><th>Active uploaded grid</th><th>Upload?</th><th></th></tr>'+
  inss.map(function(i){var d=v.insurers[i],o=d.active_override;
   return '<tr><td>'+esc(i)+'</td><td>'+d.baked_rows+'</td>'+
    '<td>'+(o?esc(o.filename||'?')+' · '+esc(o.uploaded_at||'')+' · '+esc(o.rate_rows)+' rate rows'+(o.effective_from?' · w.e.f '+esc(o.effective_from):''):'<small>(deploy-time grid active)</small>')+'</td>'+
    '<td>'+(d.uploadable?'✓':'<small>'+esc(d.note)+'</small>')+'</td>'+
    '<td>'+(o?'<button type=button class=no data-rev="'+esc(i)+'" style="margin:0;padding:3px 8px">revert</button>':'')+'</td></tr>';
  }).join('')+'</table>';
 html+='<div style="margin-top:16px;padding:12px;border:1px solid #2a2f3a;border-radius:8px;max-width:560px">'+
  '<label>Insurer</label><select id=up_ins>'+inss.filter(function(i){return v.insurers[i].uploadable;})
    .map(function(i){return '<option>'+esc(i)+'</option>';}).join('')+'</select>'+
  '<label>New grid file (.xlsx)</label><input type=file id=up_file accept=".xlsx">'+
  '<label>Effective from (optional)</label><input id=up_eff placeholder="e.g. 2026-07-01">'+
  '<button type=button id=up_prev>Preview extraction</button>'+
  '<div id=up_out></div></div>';
 p.innerHTML=html;
 var revs=p.querySelectorAll('button[data-rev]');
 for(var i=0;i<revs.length;i++){(function(b){b.addEventListener('click',function(){
   if(!confirm('Revert '+b.getAttribute('data-rev')+' to the deploy-time grid?'))return;
   fetch('/upload',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({insurer:b.getAttribute('data-rev'),mode:'revert'})})
   .then(function(r){return r.json();}).then(function(){reloadData();show('upload');});
  });})(revs[i]);}
 $('up_file').addEventListener('change',function(){
   var f=this.files[0]; UPNAME=f?f.name:''; UPB64='';
   if(f)fileB64(f,function(b){UPB64=b;setStatus('file ready: '+UPNAME+' ('+Math.round(b.length*3/4/1024)+'KB)',false);});
 });
 $('up_prev').addEventListener('click',function(){doUpload('preview');});
}
function doUpload(mode){
 if(!UPB64){setStatus('choose a file first',true);return;}
 setStatus(mode==='commit'?'committing…':'extracting…',false);
 fetch('/upload',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({insurer:val('up_ins'),mode:mode,filename:UPNAME,data_b64:UPB64,
   effective_from:val('up_eff'),uploaded_by:reviewer()})})
 .then(function(r){return r.json();})
 .then(function(rep){
   var o=$('up_out');
   if(!rep.ok){o.innerHTML='<div class=err>'+esc(rep.error)+'</div>';setStatus('upload failed',true);return;}
   var s=rep.stats,d=rep.diff;
   var html='<div class=res style="background:#10182a;border:1px solid #2a4a7a;margin-top:12px">'+
    '<b>'+esc(rep.insurer)+'</b> — '+s.rate_rows+' rate rows, '+s.elig_rows+' eligibility, '+s.warnings+' warnings'+
    '<br><small>pay range '+esc(s.pay_min)+'–'+esc(s.pay_max)+'% · '+s.n_zero+' zero-pct · '+
    Object.keys(s.by_category).map(function(k){return k+':'+s.by_category[k];}).join(' · ')+'</small>'+
    '<br><small>vs current: '+d.unchanged+' unchanged · <b>'+d.changed+' rate changes</b> · '+d.added+' added · '+d.removed+' removed</small>';
   if((d.sample_changes||[]).length){
     html+='<table style="margin-top:8px"><tr><th>Scope</th><th>Old %</th><th>New %</th></tr>'+
      d.sample_changes.map(function(c){return '<tr><td><small>'+esc(c.scope)+'</small></td><td>'+esc(c.old)+'</td><td><b>'+esc(c.new)+'</b></td></tr>';}).join('')+'</table>';
   }
   if((rep.extraction_warnings||[]).length){
     html+='<div style="margin-top:8px;color:#e7c84b"><small>'+rep.extraction_warnings.slice(0,8).map(function(w){return '⚠ '+esc(w.issue);}).join('<br>')+'</small></div>';
   }
   if(rep.mode==='preview'){
     html+='<button type=button id=up_commit style="background:#1d7a45">Commit — make this the active '+esc(rep.insurer)+' grid</button>';
   }else{
     html+='<div style="margin-top:10px"><b>✓ committed</b>'+(rep.persisted?'':' — <span style="color:#ff8a8a">'+esc(rep.warning)+'</span>')+'</div>';
   }
   html+='</div>';
   o.innerHTML=html;
   var cb=$('up_commit'); if(cb)cb.addEventListener('click',function(){doUpload('commit');});
   if(rep.mode==='commit'){reloadData();}
   setStatus(rep.mode==='commit'?'grid committed for '+rep.insurer:'preview ready — review the diff, then commit',false);
 })
 .catch(function(e){$('up_out').innerHTML='<div class=err>'+esc(e)+'</div>';setStatus('upload error',true);});
}
function rStatus(cid){var r=CAT.review[cid];return r&&r.status?r.status:'PENDING';}
function rPct(rule){var r=CAT.review[rule.catalog_id];return (r&&r.pay_in_pct!=null)?r.pay_in_pct:rule.pay_in_pct;}
function renderReview(){
 var p=$('panel');
 var ins=val('insurer');
 // review scope follows the insurer selector, like every other tab
 var rules=CAT.rules.filter(function(r){return !ins||r.insurer===ins;});
 var total=rules.length, done=0;
 for(var i=0;i<rules.length;i++){var s=rStatus(rules[i].catalog_id);if(s==='CONFIRMED'||s==='REJECTED')done++;}
 var pct=total?Math.round(done*100/total):0;
 var view=applyFilt(rules,FILT.review);
 var html='<div class=rbar>'+
  '<b>'+done+' / '+total+' reviewed</b> <small>('+esc(ins||'all insurers')+')</small>'+
  '<div class=prog><i style="width:'+pct+'%"></i></div>'+
  '<small>showing '+view.length+'</small>'+
  '<button type=button id=rexport style="margin:0;padding:6px 12px">Export approved</button>'+
  '<small id=rdl style="flex-basis:100%"></small></div>'+
  '<div class=rbar>'+filtBar('review',rules)+'</div>';
 var rows=view.slice(0,400).map(function(r){
   var s=rStatus(r.catalog_id);
   var isRate=r.rule_type==='RATE';
   var pctIn=isRate?('<input id="pct_'+r.catalog_id+'" style="width:54px" value="'+esc(rPct(r))+'">'):'';
   var reasonIn='<input id="rsn_'+r.catalog_id+'" value="'+esc((CAT.review[r.catalog_id]&&CAT.review[r.catalog_id].reason)||r.reason||'')+'">';
   return '<tr>'+
     '<td><span class="badge b-'+s+'">'+s+'</span></td>'+
     '<td>'+esc(r.catalog_id)+'</td>'+
     '<td>'+esc(r.effect)+'</td>'+
     '<td><small>'+esc(r.category)+'</small><br>'+esc(r.sub_segment)+' '+esc(r.policy_type)+
       ((r.cc_min!==''||r.cc_max!=='')?' <small>cc'+esc(r.cc_min)+'-'+esc(r.cc_max||'+')+'</small>':'')+
       ((r.age_min!==''||r.age_max!=='')?' <small>age'+esc(r.age_min)+'-'+esc(r.age_max||'+')+'</small>':'')+'</td>'+
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
 bindFilt('review');
 $('rexport').addEventListener('click',function(){
   setStatus('preparing export…',false);
   fetch('/export/summary').then(function(r){return r.json();})
   .then(function(s){
     setStatus('exported · '+s.confirmed+' confirmed, '+s.rejected+' dropped, '+s.pending+' pending → '+s.exported+' rows',false);
     var dl=$('rdl'); if(dl){
       dl.innerHTML='Download: '+['csv','xlsx','json'].map(function(f){
         return '<a href="/export/approved.'+f+'" download style="color:#6cf;margin:0 8px">'+f.toUpperCase()+'</a>';
       }).join('');
     }
     var a=document.createElement('a'); a.href='/export/approved.csv'; a.setAttribute('download','rules_catalog_approved.csv');
     document.body.appendChild(a); a.click(); document.body.removeChild(a);
   }).catch(function(e){setStatus('export error: '+e,true);});
 });
 var bs=p.querySelectorAll('.rtbl button');
 for(var i=0;i<bs.length;i++){(function(b){b.addEventListener('click',function(){
   saveReview(b.getAttribute('data-id'),b.getAttribute('data-act'));});})(bs[i]);}
}
function saveReview(cid,status){
 var body={catalog_id:cid,status:status,reviewer:reviewer()};
 var pe=$('pct_'+cid); if(pe&&pe.value!=='')body.pay_in_pct=+pe.value;
 var re=$('rsn_'+cid); if(re)body.reason=re.value;
 fetch('/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
 .then(function(r){return r.json();})
 .then(function(res){
   if(res.ok){CAT.review[cid]=res.entry;renderReview();
     setStatus('saved '+cid+' = '+status+' · '+res.reviewed+' reviewed'+(res.persisted?'':' (NOT persisted: KV not configured)'),!res.persisted);}
   else setStatus('save failed: '+(res.error||'?'),true);
 })
 .catch(function(e){setStatus('save error: '+e,true);});
}
function boot(){
 Promise.all([fetch('/meta').then(function(r){return r.json();}),
              fetch('/rules').then(function(r){return r.json();}),
              fetch('/catalog').then(function(r){return r.json();}),
              fetch('/options').then(function(r){return r.json();})])
 .then(function(res){
   META=res[0]; RULES=res[1]; CAT=res[2]; OPT=res[3];
   var s=$('state');
   s.innerHTML='<option value="">(any)</option>'+META.states.map(function(x){return '<option>'+esc(x)+'</option>';}).join('');
   var iorder=['SBI_GENERAL','CHOLA_MS','GODIGIT','ICICI_LOMBARD','HDFC_ERGO','TATA_AIG','UNITED_INDIA','CAT_B'];
   var inss=Object.keys(OPT).sort(function(a,b){return (iorder.indexOf(a)+1||9)-(iorder.indexOf(b)+1||9);});
   fillSel('insurer',inss,false);
   onIns();
   show('rate');
   var warn=CAT.persisted?'':' · ⚠ KV not configured (review not shared)';
   setStatus('connected · '+CAT.rules.length+' catalog rules · '+inss.length+' insurers'+warn,false);
 })
 .catch(function(e){ setStatus('failed to load: '+e,true); });
}
function runQuote(){
 setStatus('resolving…',false);
 var risk={insurer:val('insurer'),category:val('category'),sub_segment:val('sub_segment'),policy_type:val('policy_type'),
  make:val('make'),model:val('model'),rto_code:val('rto_code'),cluster:val('cluster'),state:val('state'),
  cc:val('cc')?+val('cc'):null,age_years:val('age_years')!==''?+val('age_years'):null};
 fetch('/resolve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(risk)})
 .then(function(resp){ if(!resp.ok) throw new Error('HTTP '+resp.status); return resp.json(); })
 .then(function(r){
   var html='<div class="res '+r.decision+'">';
   if(r.decision==='ALLOW'){
     var m=r.matched||{};
     html+='<div class=big>'+esc(r.pay_in_pct)+'% <small>on '+esc(r.applies_on||'OD')+'</small></div>'+
       '<div><small>rule '+esc(r.rate_rule)+' · '+esc(m.sub_segment)+
       (m.policy_type?' · '+esc(m.policy_type):'')+(m.make?' · '+esc(m.make):'')+
       (m.geo_label?' · '+esc(m.geo_label):'')+'</small></div>'+
       '<div><small>source '+esc(m.source_sheet)+'!'+esc(m.source_cell)+'</small></div>';
     if((r.declines||[]).length){
       html+='<div style="margin-top:8px;color:#ff8a8a"><small>⚠ also matched '+r.declines.length+
         ' decline rule(s): '+r.declines.map(function(x){return esc(x.reason||x.source_text);}).join('; ')+'</small></div>';
     }
     if(r.n_candidates>1) html+=candTable(r.candidates||[],r.n_candidates);
   }else if(r.decision==='DECLINE'){
     html+='<div class=big>DECLINED</div>'+
       (r.declines||[]).map(function(x){return '<div>• '+esc(x.reason||x.source_text)+
         ' <small>('+esc(x.source_sheet)+'!'+esc(x.source_cell)+')</small></div>';}).join('');
   }else{
     html+='<div class=big>No rate</div><small>no catalog rule matched these inputs</small>';
     if((r.declines||[]).length) html+='<div><small>'+r.declines.length+' decline rule(s) matched</small></div>';
   }
   $('out').innerHTML=html+'</div>';
   setStatus('done · '+r.decision+(r.n_candidates?' · '+r.n_candidates+' candidate(s)':''),false);
 })
 .catch(function(e){ $('out').innerHTML='<div class=err>Request failed: '+esc(e)+'</div>'; setStatus('error',true); });
}
document.addEventListener('DOMContentLoaded',function(){
 $('calc').addEventListener('click',runQuote);
 $('insurer').addEventListener('change',onIns);
 $('category').addEventListener('change',onCat);
 $('sub_segment').addEventListener('change',onSub);
 var btns=document.querySelectorAll('.tabs button');
 for(var i=0;i<btns.length;i++){
   (function(b){ b.addEventListener('click',function(){show(b.getAttribute('data-tab'));}); })(btns[i]);
 }
 boot();
});
</script></body></html>"""
