let studyChart;

function studyForm(player) {
  return `<form class="form-card study-form" data-player-id="${player.player_id}">
    <input class="input" name="subject" placeholder="Subject" required>
    <textarea class="textarea" name="notes" placeholder="Notes (optional)"></textarea>
    <div class="form-actions"><button class="small-primary">Post study entry</button></div>
  </form>`;
}

function educationCard(player) {
  const entries = player.entries.length ? player.entries.map(entry => `<div class="entry-row" data-entry-id="${entry.id}" data-player-id="${player.player_id}"><div><strong>${escapeHtml(entry.subject)}</strong><small>${escapeHtml(entry.notes || 'No notes')} · ${entry.day}</small></div><div class="entry-row-actions"><span class="entry-value">note</span><button class="entry-delete-btn" data-entry-id="${entry.id}" title="Delete entry" aria-label="Delete">🗑</button></div></div>`).join('') : '<div class="empty-state">No study entries yet.</div>';
  return `<article class="duo-player-card glass-panel ${player.player_id === 2 ? 'player-2-card':''}">
    <div class="duo-card-head"><div><span class="mono-label">PLAYER ${String(player.player_id).padStart(2,'0')}</span><h2>${escapeHtml(player.name)}</h2></div><span class="player-badge">📚</span></div>
    <div class="card-stat-row"><div class="stat-box"><span>Today</span><strong>${player.today_minutes}m</strong></div><div class="stat-box"><span>Entries</span><strong>${player.entries.length}</strong></div><div class="stat-box"><span>Unit</span><strong>1:1</strong></div></div>
    <div class="section-title"><div><span class="mono-label">RECENT STUDY</span></div></div><div class="entry-list">${entries}</div>
    ${studyForm(player)}
  </article>`;
}

async function loadEducation() {
  const data = await Duo.api('/api/education');
  document.getElementById('educationColumns').innerHTML = data.players.map(educationCard).join('');
  document.querySelectorAll('.study-form').forEach(form => form.addEventListener('submit', async event => {
    event.preventDefault();
    const fd = new FormData(form);
    try {
      await Duo.api('/api/education/entries', { method:'POST', body:JSON.stringify({ player_id:Number(form.dataset.playerId), subject:fd.get('subject'), notes:fd.get('notes') }) });
      Duo.toast('Study entry posted.'); await refreshEducation();
    } catch (e) { Duo.toast(e.message); }
  }));
  // Delete entry buttons
  document.querySelectorAll('.entry-delete-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Delete this study entry?')) return;
      try {
        await Duo.api(`/api/education/entries/${btn.dataset.entryId}`, { method: 'DELETE' });
        Duo.toast('Entry deleted.');
        await refreshEducation();
      } catch (e) { Duo.toast(e.message); }
    });
  });
  renderStudyTotal(data.players);
}

function renderStudyTotal(players) {
  const bar = document.getElementById('studyTotalBar');
  bar.innerHTML = players.map(player => `<div class="total-player"><div class="total-top"><div><span class="mono-label">${escapeHtml(player.name)} · TODAY</span><strong>${player.today_minutes} minutes</strong></div><span class="tag">study points</span></div><div class="bar"><div class="fill" style="width:${Math.min(100, player.today_minutes/300*100)}%"></div></div><div class="total-edit"><input class="input total-minutes" type="number" min="0" max="1440" value="${player.today_minutes}"><button class="small-primary update-total" data-player-id="${player.player_id}">Update total</button></div></div>`).join('');
  document.querySelectorAll('.update-total').forEach(button => button.addEventListener('click', async () => {
    const input = button.parentElement.querySelector('.total-minutes');
    try { await Duo.api('/api/education/today', { method:'PUT', body:JSON.stringify({ player_id:Number(button.dataset.playerId), minutes:Number(input.value || 0) }) }); Duo.toast('Today’s total saved.'); await refreshEducation(); } catch (e) { Duo.toast(e.message); }
  }));
}

async function renderStudyChart() {
  const data = await Duo.api('/api/charts?days=14');
  const ctx = document.getElementById('studyChart');
  if (studyChart) studyChart.destroy();
  const datasets = data.players.map((player, index) => ({ label: player.name, data: player.study, tension:.35, borderWidth:2, fill:false, borderColor:index === 0 ? '#5867ff' : '#ed4db6' }));
  studyChart = new Chart(ctx, { type:'line', data:{ labels:data.labels.map(d => d.slice(5)), datasets }, options:{ responsive:true, plugins:{ legend:{ labels:{ color:getComputedStyle(document.body).getPropertyValue('--muted') } } }, scales:{ x:{ ticks:{ color:getComputedStyle(document.body).getPropertyValue('--muted') }, grid:{ color:'rgba(100,110,140,.08)' } }, y:{ beginAtZero:true, ticks:{ color:getComputedStyle(document.body).getPropertyValue('--muted') }, grid:{ color:'rgba(100,110,140,.08)' } } } } });
}

async function refreshEducation() { await loadEducation(); await renderStudyChart(); await Duo.loadState(); }

(async function(){ try { await refreshEducation(); } catch(e) { Duo.toast(e.message); } })();
function escapeHtml(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
