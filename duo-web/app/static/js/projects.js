function projectSummaryCard(project, state) {
  const tasks = project.tasks.length; const done = project.tasks.filter(t=>t.completed).length;
  return `<article class="project-summary-card glass-panel"><span class="mono-label">${project.icon} ACTIVE FILE</span><div class="summary-number">${project.progress}%</div><strong>${escapeHtml(project.name)}</strong><p>${escapeHtml(project.aim)}</p><div class="project-player-compare">${state.players.map(p=>{const x=project.per_player[p.id]||{completed:0,total:0};return `<span class="mini-chip">${escapeHtml(p.name)} · ${x.completed}/${x.total}</span>`}).join('')}</div></article>`;
}

function projectRow(project, state) {
  const chips = state.players.map(p=>{const x=project.per_player[p.id]||{completed:0,total:0};return `<span class="mini-chip">${escapeHtml(p.name)} ${x.completed}/${x.total}</span>`}).join('');
  return `<div class="project-row"><div class="project-mark">${project.icon}</div><div><h3>${escapeHtml(project.name)}</h3><p>${escapeHtml(project.aim)}</p><div class="project-player-compare">${chips}</div></div><div class="project-progress-wrap"><div class="progress-line"><span>${project.progress}% complete</span><span>${project.tasks.filter(t=>t.completed).length}/${project.tasks.length} missions</span></div><div class="bar"><div class="fill" style="width:${project.progress}%"></div></div></div><a class="secondary-btn project-open" href="/projects/${project.id}">Open file ↗</a></div>`;
}

async function loadProjects(){
  const state = Duo.state || await Duo.loadState();
  const data = await Duo.api('/api/projects');
  document.getElementById('projectSummary').innerHTML = data.projects.map(p=>projectSummaryCard(p,state)).join('');
  document.getElementById('projectList').innerHTML = data.projects.length ? data.projects.map(p=>projectRow(p,state)).join('') : '<div class="empty-state">No projects yet. Create your first shared file.</div>';
}
(async function(){ try { await Duo.loadState(); await loadProjects(); } catch(e){ Duo.toast(e.message); } })();
function escapeHtml(value){ return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
