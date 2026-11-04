(function(){
const D = window.SITE_DATA || {commits:{},notes:[],docs:[],metrics:[],runs:[],recent:[]};
const $ = id => document.getElementById(id);
$('upd').textContent = D.updated || 'never';
const days = Object.keys(D.commits).sort(), totalCommits = days.reduce((a,d)=>a+D.commits[d],0);
const last = D.metrics.length ? D.metrics[D.metrics.length-1] : null;
function tile(v,l){return '<div class="tile"><b>'+v+'</b>'+l+'</div>';}
$('strip').innerHTML = tile(days.length,'working days')+tile(totalCommits,'commits')+tile(D.notes.length,'daily notes')+
  tile(last?(last.passed+'/'+(last.passed+last.failed)):'n/a','tests passing')+tile(D.runs.length,'pipeline runs');
function bars(svg, labels, vals, color){
  const W=900,H=220,pad=30,n=Math.max(1,vals.length),bw=(W-2*pad)/n,mx=Math.max(1,...vals);
  let s='<line x1="'+pad+'" y1="'+(H-pad)+'" x2="'+(W-pad)+'" y2="'+(H-pad)+'" stroke="currentColor" opacity=".3"/>';
  vals.forEach((v,i)=>{const h=(H-2*pad)*v/mx;s+='<rect x="'+(pad+i*bw+2)+'" y="'+(H-pad-h)+'" width="'+Math.max(1,bw-4)+'" height="'+h+'" fill="'+color+'"><title>'+labels[i]+': '+v+'</title></rect>';});
  if(!vals.length) s+='<text x="'+W/2+'" y="'+H/2+'" text-anchor="middle" fill="currentColor" opacity=".5">no data yet</text>';
  $(svg).innerHTML=s;}
bars('commits',days,days.map(d=>D.commits[d]),'var(--acc)');
bars('tests',D.metrics.map(m=>m.date),D.metrics.map(m=>m.passed),'var(--ok)');
$('testsnote').textContent = D.metrics.length ? '' : 'Test counts appear once check.sh records them in notes/metrics.jsonl.';
$('runs').innerHTML = D.runs.length ? D.runs.slice(-8).reverse().map(r=>'<div>'+(r.night||'?')+': in '+r.rowsIn+', valid '+r.valid+', quarantined '+r.quarantined+(r.hash?' <span class="badge">'+String(r.hash).slice(0,12)+'</span>':'')+'</div>').join('') : '<span class="sub">The first pipeline run appears here after Sprint 1 (Day 5).</span>';
$('notes').innerHTML = D.notes.length ? D.notes.slice().reverse().map(n=>'<div class="card"><b>'+n.title+'</b> <span class="badge">'+n.words+' words</span><div class="sub">'+n.excerpt+'</div></div>').join('') : '<div class="card sub">Daily notes will appear here from Day 1 (Thursday, Nov 5, 2026).</div>';
$('q').addEventListener('input',e=>{const q=e.target.value.toLowerCase().split(/\s+/).filter(Boolean);
  if(!q.length){$('hits').innerHTML='';return;}
  const sc=D.docs.map(d=>{const t=(d.title+' '+d.text).toLowerCase();let s=0;q.forEach(w=>{const m=t.split(w).length-1;s+=m;if(d.title.toLowerCase().includes(w))s+=5;});return {d,s};}).filter(x=>x.s>0).sort((a,b)=>b.s-a.s).slice(0,6);
  $('hits').innerHTML = sc.length ? sc.map(x=>'<div class="hit"><a href="https://github.com/aimozart/hippagrchealthcare/blob/main/'+x.d.path+'">'+x.d.title+'</a> <span class="badge">'+x.d.path+'</span><div class="sub">'+x.d.text.slice(0,200)+'…</div></div>').join('') : '<div class="sub">No matches.</div>';});
})();
