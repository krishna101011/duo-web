const projectId = window.DUO_PROJECT_ID;
let projectData;

function renderProject(data) {
  projectData = data;
  document.getElementById('projectProgressValue').textContent = `${data.progress}%`;
  document.getElementById('projectProgressFill').style.width = `${data.progress}%`;
  const state = Duo.state || {players:[]};
  document.getElementById('projectPlayerStats').innerHTML = state.players.map((p,index)=>{
    const mine = data.per_player[p.id] || {completed:0,total:0};
    const notes = data.notes.filter(n=>n.player_id===p.id).length;
    return `<article class="duo-project-card glass-panel"><span class="mono-label">PLAYER ${String(index+1).padStart(2,'0')}</span><h3>${escapeHtml(p.name)}</h3><div class="big-stat">${mine.completed}/${mine.total}</div><div class="tiny-note">missions completed · ${notes} progress notes</div><div class="bar"><div class="fill ${index?'hot':''}" style="width:${mine.total?mine.completed/mine.total*100:0}%"></div></div></article>`;
  }).join('');

  const taskList = document.getElementById('taskList');
  taskList.innerHTML = data.tasks.length ? data.tasks.map(task=>{
    const assignee = state.players.find(p=>p.id===task.assignee_id);
    return `<div class="task-item ${task.completed?'completed':''}"><button class="task-check" data-task-id="${task.id}" data-next="${!task.completed}">${task.completed?'✓':''}</button><div><div class="task-title">${escapeHtml(task.title)}</div><div class="task-assignee">${assignee?escapeHtml(assignee.name):'shared'}</div></div><span class="tag">${task.completed?'done':'open'}</span></div>`;
  }).join('') : '<div class="empty-state">No missions yet. Add the first one.</div>';
  taskList.querySelectorAll('.task-check').forEach(button=>button.addEventListener('click',async()=>{
    try { await Duo.api(`/api/projects/tasks/${button.dataset.taskId}`,{method:'PATCH',body:JSON.stringify({completed:button.dataset.next==='true'})}); Duo.toast(button.dataset.next==='true'?'Mission completed! +25 XP':'Mission reopened.'); await refreshProject(); if(button.dataset.next==='true') confetti(); } catch(e){ Duo.toast(e.message); }
  }));

  document.getElementById('notesList').innerHTML = data.notes.length ? data.notes.map(n=>{const p=state.players.find(x=>x.id===n.player_id);return `<article class="note-item"><header><strong>${escapeHtml(p?.name || 'Player')}</strong><time>${n.day}</time></header><p>${escapeHtml(n.note)}</p></article>`;}).join('') : '<div class="empty-state">No progress notes yet.</div>';
  document.getElementById('noteForms').innerHTML = state.players.map(p=>`<form class="note-form form-card" data-player-id="${p.id}"><span class="mono-label">${escapeHtml(p.name)}</span><textarea class="textarea" name="note" placeholder="What moved today?" required></textarea><div class="form-actions"><button class="small-primary">Post note</button></div></form>`).join('');
  document.querySelectorAll('.note-form').forEach(form=>form.addEventListener('submit',async event=>{event.preventDefault();const text=form.querySelector('textarea').value;try{await Duo.api(`/api/projects/${projectId}/notes`,{method:'POST',body:JSON.stringify({player_id:Number(form.dataset.playerId),note:text})});Duo.toast('Progress note posted.');await refreshProject();}catch(e){Duo.toast(e.message);}}));
}

function addTaskModal(){
  const root=document.getElementById('taskModal');root.hidden=false;root.innerHTML=`<div class="modal-shell"><div class="modal-card"><div class="modal-head"><div><h3>Add a mission</h3><p>Assign it to one player or keep it shared.</p></div><button class="modal-close" id="closeTask">×</button></div><label class="field-label">Mission title</label><input class="input" id="taskTitle" placeholder="Ship the next useful thing"><label class="field-label">Assignee</label><select class="select" id="taskAssignee"></select><div class="modal-actions"><button class="secondary-btn" id="cancelTask">Cancel</button><button class="primary-btn" id="saveTask">Add mission</button></div></div></div>`;
  const select=root.querySelector('#taskAssignee');select.innerHTML='<option value="">Shared</option>'+(Duo.state?.players||[]).map(p=>`<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
  root.querySelectorAll('#closeTask,#cancelTask').forEach(b=>b.addEventListener('click',()=>{root.hidden=true;root.innerHTML='';}));
  root.querySelector('#saveTask').addEventListener('click',async()=>{try{await Duo.api(`/api/projects/${projectId}/tasks`,{method:'POST',body:JSON.stringify({title:root.querySelector('#taskTitle').value,assignee_id:select.value?Number(select.value):null})});root.hidden=true;root.innerHTML='';Duo.toast('Mission added.');await refreshProject();}catch(e){Duo.toast(e.message);}});
}

async function refreshProject(){ projectData=await Duo.api(`/api/projects/${projectId}`); renderProject(projectData); }
function confetti(){
  const layer=document.createElement('div');layer.style.cssText='position:fixed;inset:0;pointer-events:none;z-index:99;overflow:hidden;';
  for(let i=0;i<48;i++){const piece=document.createElement('i');piece.textContent='✦';piece.style.cssText=`position:absolute;left:${Math.random()*100}%;top:-10px;font-size:${8+Math.random()*11}px;color:${['#5867ff','#13c8aa','#ed4db6','#dbad34'][i%4]};animation:fall ${1.3+Math.random()*1.5}s ease-out ${Math.random()*.15}s forwards;`;layer.appendChild(piece);}
  const style=document.createElement('style');style.textContent='@keyframes fall{to{transform:translateY(110vh) rotate(540deg);opacity:0}}';layer.appendChild(style);document.body.appendChild(layer);setTimeout(()=>layer.remove(),3000);
}
document.getElementById('addTaskButton')?.addEventListener('click',addTaskModal);document.getElementById('detailRefresh')?.addEventListener('click',()=>refreshProject());
(async function(){try{await Duo.loadState();await refreshProject();}catch(e){Duo.toast(e.message);}})();
function escapeHtml(value){return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
