(async function(){
  const tabId=window.DUO_CONFIG.customTabId;
  try{await renderCustom(tabId);}catch(e){Duo.toast(e.message);}
})();

function formFor(tab, player){
  const type=tab.tracking_type;
  let field='';
  if(type==='time log') field='<input class="input" name="value" type="number" min="0" placeholder="Minutes">';
  if(type==='numeric counter') field='<input class="input" name="value" type="number" step="1" placeholder="Count">';
  if(type==='checklist') field='<select class="select" name="value"><option value="1">Done</option><option value="0">Not done</option></select>';
  if(type==='notes') field='<input class="input" name="value" type="number" value="0" hidden><textarea class="textarea" name="note" placeholder="Write a note…"></textarea>';
  return `<form class="form-card custom-form" data-player-id="${player.player_id}"><input class="input" name="label" placeholder="${type==='notes'?'Entry title':'What did you track?'}" required style="margin-bottom:7px">${field}<div class="form-actions"><button class="small-primary">Add entry</button></div></form>`;
}

function cardFor(tab, player){
  const entries=player.entries.length?player.entries.map(e=>`<div class="entry-row"><div><strong>${escapeHtml(e.label)}</strong><small>${e.day}${e.note?` · ${escapeHtml(e.note)}`:''}</small></div><span class="entry-value">${tab.tracking_type==='checklist'?(e.value?'✓':'—'):tab.tracking_type==='notes'?'note':e.value}</span></div>`).join(''):'<div class="empty-state">No entries yet.</div>';
  return `<article class="duo-player-card glass-panel"><div class="duo-card-head"><div><span class="mono-label">PLAYER ${String(player.player_id).padStart(2,'0')}</span><h2>${escapeHtml(player.name)}</h2></div><span class="player-badge">${escapeHtml(tab.icon)}</span></div><div class="entry-list">${entries}</div>${formFor(tab,player)}</article>`;
}

async function renderCustom(tabId){
  const data=await Duo.api(`/api/custom-tabs/${tabId}`);document.getElementById('customColumns').innerHTML=data.players.map(p=>cardFor(data.tab,p)).join('');
  document.querySelectorAll('.custom-form').forEach(form=>form.addEventListener('submit',async event=>{event.preventDefault();const fd=new FormData(form);try{await Duo.api(`/api/custom-tabs/${tabId}/entries`,{method:'POST',body:JSON.stringify({player_id:Number(form.dataset.playerId),label:fd.get('label'),value:Number(fd.get('value')||0),note:fd.get('note')||''})});Duo.toast('Entry added.');await renderCustom(tabId);await Duo.loadState();}catch(e){Duo.toast(e.message);}}));
}
function escapeHtml(value){return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
