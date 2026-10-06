let workoutChart;

function fitnessForm(player) {
  return `<form class="form-card fitness-form" data-player-id="${player.player_id}"><div class="form-grid"><input class="input" name="activity" placeholder="Activity" required><input class="input" name="duration_minutes" type="number" min="1" max="1440" placeholder="Minutes" required></div><div class="form-actions"><button class="small-primary">Log activity</button></div></form>`;
}

function fitnessCard(player) {
  const entries = player.entries.length ? player.entries.map(entry => `<div class="entry-row" data-entry-id="${entry.id}"><div><strong>${escapeHtml(entry.activity)}</strong><small>${entry.day}</small></div><div class="entry-row-actions"><span class="entry-value">${entry.duration_minutes}m</span><button class="entry-delete-btn" data-entry-id="${entry.id}" title="Delete" aria-label="Delete">🗑</button></div></div>`).join('') : '<div class="empty-state">No activity logged yet.</div>';
  return `<article class="duo-player-card glass-panel ${player.player_id === 2 ? 'player-2-card':''}">
    <div class="duo-card-head"><div><span class="mono-label">PLAYER ${String(player.player_id).padStart(2,'0')}</span><h2>${escapeHtml(player.name)}</h2></div><span class="player-badge">🏃</span></div>
    <div class="card-stat-row"><div class="stat-box"><span>Today</span><strong>${player.today_minutes}m</strong></div><div class="stat-box"><span>Logs</span><strong>${player.entries.length}</strong></div><div class="stat-box"><span>Points</span><strong>${player.today_minutes}</strong></div></div>
    <div class="section-title"><div><span class="mono-label">RECENT ACTIVITY</span></div></div><div class="entry-list">${entries}</div>${fitnessForm(player)}
  </article>`;
}

async function loadFitness() {
  const data = await Duo.api('/api/fitness');
  document.getElementById('fitnessColumns').innerHTML = data.players.map(fitnessCard).join('');
  document.querySelectorAll('.fitness-form').forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault(); const fd = new FormData(form);
    try { await Duo.api('/api/fitness', { method:'POST', body:JSON.stringify({ player_id:Number(form.dataset.playerId), activity:fd.get('activity'), duration_minutes:Number(fd.get('duration_minutes')) }) }); Duo.toast('Activity logged.'); await refreshFitness(); } catch(e){ Duo.toast(e.message); }
  }));
  // Delete entry buttons
  document.querySelectorAll('.entry-delete-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Delete this activity entry?')) return;
      try {
        await Duo.api(`/api/fitness/${btn.dataset.entryId}`, { method: 'DELETE' });
        Duo.toast('Activity deleted.');
        await refreshFitness();
      } catch (e) { Duo.toast(e.message); }
    });
  });
}

async function renderWorkoutChart() {
  const data = await Duo.api('/api/charts?days=14'); const ctx = document.getElementById('workoutChart');
  if (workoutChart) workoutChart.destroy();
  const datasets = data.players.map((player,index)=>({label:player.name,data:player.workout,tension:.35,borderWidth:2,fill:false,borderColor:index===0?'#13c8aa':'#ed4db6'}));
  workoutChart = new Chart(ctx,{type:'line',data:{labels:data.labels.map(d=>d.slice(5)),datasets},options:{responsive:true,plugins:{legend:{labels:{color:getComputedStyle(document.body).getPropertyValue('--muted')}}},scales:{x:{ticks:{color:getComputedStyle(document.body).getPropertyValue('--muted')},grid:{color:'rgba(100,110,140,.08)'}},y:{beginAtZero:true,ticks:{color:getComputedStyle(document.body).getPropertyValue('--muted')},grid:{color:'rgba(100,110,140,.08)'}}}}});
}
async function refreshFitness(){ await loadFitness(); await renderWorkoutChart(); await Duo.loadState(); }
(async function(){ try { await refreshFitness(); } catch(e){ Duo.toast(e.message); } })();
function escapeHtml(value){ return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
