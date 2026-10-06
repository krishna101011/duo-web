/* Shared client helpers. No build step is required. */
const Duo = {
  state: null,
  async api(url, options = {}) {
    const config = { ...options, headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) } };
    const response = await fetch(url, config);
    let data = {};
    try { data = await response.json(); } catch (_) { /* csv / empty response */ }
    if (!response.ok) {
      throw new Error(data.detail || data.message || `Request failed (${response.status})`);
    }
    return data;
  },
  toast(message) {
    const node = document.getElementById('toast');
    if (!node) return;
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(window.__duoToast);
    window.__duoToast = setTimeout(() => node.classList.remove('show'), 1800);
  },
  async loadState() {
    this.state = await this.api('/api/state');
    this.applyAppearance(this.state.background);
    this.renderTop(this.state.players);
    return this.state;
  },
  applyAppearance(background) {
    if (!background) return;
    document.body.dataset.theme = background.theme || 'glass';
    const value = background.background_value || 'aurora';
    if (background.background_type === 'image') {
      document.body.style.background = `center / cover fixed no-repeat url('${value}')`;
      return;
    }
    if (background.background_type === 'solid') {
      document.body.style.background = value;
      return;
    }
    document.body.style.background = gradientFor(value, document.body.dataset.theme);
  },
  renderTop(players) {
    const a = players?.[0];
    const b = players?.[1];
    if (a) this.renderPlayerTop(a, 1);
    if (b) this.renderPlayerTop(b, 2);
    if (a && b) {
      const topStudy = document.getElementById('topStudy');
      const topWorkout = document.getElementById('topWorkout');
      const topPoints = document.getElementById('topPoints');
      const topStreak = document.getElementById('topStreak');
      if (topStudy) topStudy.textContent = `${a.study_minutes}m / ${b.study_minutes}m`;
      if (topWorkout) topWorkout.textContent = `${a.workout_minutes}m / ${b.workout_minutes}m`;
      if (topPoints) topPoints.textContent = `${a.today_points} / ${b.today_points}`;
      if (topStreak) topStreak.textContent = `${a.streak}d / ${b.streak}d`;
    }
    this.loadRivalry();
  },
  renderPlayerTop(player, index) {
    const points = document.querySelector(`[data-points-id="${player.id}"]`);
    if (points) points.textContent = `${player.today_points} XP`;
    const input = document.querySelector(`.player-name[data-player-id="${player.id}"]`);
    if (input && document.activeElement !== input) input.value = player.name;
    const avatar = document.querySelector(`.player-${index} .small-avatar`);
    if (avatar) avatar.innerHTML = `${player.avatar_path ? `<img src="${escapeHtml(player.avatar_path)}" alt="${escapeHtml(player.name)} avatar">` : `<span>${escapeHtml(player.emoji)}</span>`}<input class="hidden-file avatar-upload" type="file" accept="image/png,image/jpeg,image/webp,image/gif" data-player-id="${player.id}">`;
  },
  async loadRivalry() {
    try {
      const data = await this.api('/api/rivalry');
      const nodes = [document.getElementById('topRivalry'), document.getElementById('homeRivalry')].filter(Boolean);
      nodes.forEach(node => node.textContent = data.message);
      const source = document.getElementById('rivalrySource');
      if (source) source.textContent = `Source: ${data.source}. AI is optional; templates never disappear.`;
    } catch (error) {
      const node = document.getElementById('topRivalry');
      if (node) node.textContent = 'Rivalry is ready once two players have data.';
    }
  },
  bindGlobal() {
    document.querySelectorAll('.player-name').forEach(input => {
      input.addEventListener('change', async () => {
        try {
          await this.api(`/api/players/${input.dataset.playerId}`, {
            method: 'PATCH',
            body: JSON.stringify({ name: input.value.trim(), emoji: null })
          });
          this.toast('Player name saved.');
          await this.loadState();
        } catch (error) { this.toast(error.message); }
      });
    });

    document.querySelectorAll('.avatar-upload').forEach(input => {
      input.addEventListener('change', async event => {
        const file = event.target.files?.[0];
        if (!file) return;
        const form = new FormData();
        form.append('file', file);
        try {
          await this.api(`/api/players/${input.dataset.playerId}/avatar`, { method: 'POST', body: form });
          this.toast('Avatar updated.');
          await this.loadState();
        } catch (error) { this.toast(error.message); }
      });
    });

    document.querySelectorAll('.emoji-avatar-btn').forEach(button => {
      button.addEventListener('click', async () => {
        const choices = ['🧠','⚡','🔥','🌱','📚','💡','🚀','🎯','🦊','🐺','🐼','🦉','🌊','🏋️','🎨','💻'];
        const picked = window.prompt(`Pick an emoji:\n${choices.join(' ')}`, '✨');
        if (!picked) return;
        try {
          const player = (this.state?.players || []).find(p => p.id === Number(button.dataset.playerId));
          await this.api(`/api/players/${button.dataset.playerId}`, { method:'PATCH', body:JSON.stringify({ name:player?.name || 'Player', emoji:picked.slice(0,8) }) });
          this.toast('Emoji avatar saved.');
          await this.loadState();
        } catch (error) { this.toast(error.message); }
      });
    });

    document.getElementById('themeToggle')?.addEventListener('click', async () => {
      const next = document.body.dataset.theme === 'dark' ? 'glass' : 'dark';
      const current = this.state?.background || currentBackground();
      try {
        await this.setBackground(next, current.background_type || current.type || 'gradient', current.background_value || current.value || 'aurora');
        this.toast(next === 'glass' ? 'Soft Glass mode' : 'Dark Glass mode');
      } catch (error) { this.toast(error.message); }
    });
    document.getElementById('backgroundButton')?.addEventListener('click', () => openBackgroundModal());
    document.querySelectorAll('[data-action="background"]').forEach(button => button.addEventListener('click', () => openBackgroundModal()));
    document.querySelectorAll('[data-action="create-tab"]').forEach(button => button.addEventListener('click', () => openCreateTabModal()));
    document.querySelectorAll('[data-action="create-project"]').forEach(button => button.addEventListener('click', () => openCreateProjectModal()));
    document.querySelectorAll('[data-ai]').forEach(button => button.addEventListener('click', () => this.runAi(button.dataset.ai)));
  },
  async setBackground(theme, type, value) {
    await this.api('/api/background', { method: 'POST', body: JSON.stringify({ theme, background_type: type, background_value: value }) });
    this.applyAppearance({ theme, background_type: type, background_value: value });
    if (this.state) this.state.background = { theme, background_type: type, background_value: value };
  },
  async uploadBackground(file) {
    const form = new FormData(); form.append('file', file);
    const result = await this.api('/api/background/upload', { method: 'POST', body: form });
    const current = document.body.dataset.theme || 'glass';
    this.applyAppearance({ theme: current, background_type: 'image', background_value: result.background_value });
    if (this.state) this.state.background = { theme: current, background_type: 'image', background_value: result.background_value };
    return result;
  },
  async runAi(kind) {
    const resultNode = document.getElementById('aiResult');
    if (!resultNode) return;
    resultNode.hidden = false;
    resultNode.textContent = 'Thinking…';
    try {
      const result = await this.api(`/api/ai/summary?kind=${encodeURIComponent(kind)}`);
      resultNode.textContent = result.text + `\n\n${result.source}`;
    } catch (error) { resultNode.textContent = error.message; }
  }
};

function gradientFor(value, theme = 'glass') {
  if (theme === 'dark') {
    const map = {
      aurora: 'linear-gradient(125deg,#0c1020 10%,#171c37 52%,#0b2928 100%)',
      sunset: 'linear-gradient(125deg,#17101f 5%,#5b223f 48%,#352718 100%)',
      ocean: 'linear-gradient(125deg,#0b1220 0%,#172b52 60%,#202b48 100%)'
    };
    return map[value] || value || '#0c1020';
  }
  const map = {
    aurora: 'linear-gradient(125deg,#eef3f8 0%,#dfe7ff 48%,#d8f2ed 100%)',
    sunset: 'linear-gradient(125deg,#f8e7e9 5%,#f2dff2 48%,#fff0d4 100%)',
    ocean: 'linear-gradient(125deg,#e7efff 0%,#d9f3ee 60%,#f0edff 100%)'
  };
  return map[value] || value || '#eef3f8';
}

function currentBackground() {
  const theme = document.body.dataset.theme || 'glass';
  const bg = Duo.state?.background;
  if (bg) return { theme, type:bg.background_type, value:bg.background_value };
  return { theme, type:'gradient', value:'aurora' };
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
}

function closeModalRoot() { document.getElementById('modalRoot').innerHTML = ''; }

function modal(content) {
  const root = document.getElementById('modalRoot');
  root.innerHTML = `<div class="modal-shell" data-modal-overlay><div class="modal-card">${content}</div></div>`;
  root.querySelector('[data-modal-overlay]').addEventListener('click', event => { if (event.target.dataset.modalOverlay !== undefined) closeModalRoot(); });
}

function openBackgroundModal() {
  modal(`
    <div class="modal-head"><div><h3>Customize your canvas</h3><p>Soft Glass stays the default; every selection is persisted in SQLite.</p></div><button class="modal-close" data-close>×</button></div>
    <label class="field-label">Theme</label>
    <div class="segmented" style="width:100%"><button data-theme="glass">Soft Glass</button><button data-theme="dark">Dark Glass</button></div>
    <label class="field-label">Gradient</label>
    <div class="background-choices">
      <button data-gradient="aurora"><span class="preview-bg aurora-bg"></span>Aurora</button>
      <button data-gradient="sunset"><span class="preview-bg sunset-bg"></span>Sunset</button>
      <button data-gradient="ocean"><span class="preview-bg ocean-bg"></span>Ocean</button>
      <button id="solidChoice"><span class="preview-bg" style="background:#eef3f8"></span>Solid</button>
    </div>
    <label class="field-label">Solid color</label><input id="bgColorModal" class="input" type="color" value="#eef3f8">
    <label class="field-label">Upload image</label><input id="bgImageModal" class="input" type="file" accept="image/png,image/jpeg,image/webp,image/gif">
    <div class="modal-actions"><button class="secondary-btn" data-close>Cancel</button><button class="primary-btn" data-close>Done</button></div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelectorAll('[data-theme]').forEach(btn => btn.addEventListener('click', async () => {
    try { await Duo.setBackground(btn.dataset.theme, 'gradient', 'aurora'); Duo.toast('Theme saved.'); } catch (e) { Duo.toast(e.message); }
  }));
  root.querySelectorAll('[data-gradient]').forEach(btn => btn.addEventListener('click', async () => {
    try { await Duo.setBackground(document.body.dataset.theme || 'glass', 'gradient', btn.dataset.gradient); Duo.toast(`${btn.dataset.gradient} gradient saved.`); } catch (e) { Duo.toast(e.message); }
  }));
  root.querySelector('#solidChoice').addEventListener('click', async () => {
    const value = root.querySelector('#bgColorModal').value;
    try { await Duo.setBackground(document.body.dataset.theme || 'glass', 'solid', value); Duo.toast('Solid background saved.'); } catch (e) { Duo.toast(e.message); }
  });
  root.querySelector('#bgColorModal').addEventListener('input', async event => {
    try { await Duo.setBackground(document.body.dataset.theme || 'glass', 'solid', event.target.value); } catch (e) { Duo.toast(e.message); }
  });
  root.querySelector('#bgImageModal').addEventListener('change', async event => {
    const file = event.target.files?.[0]; if (!file) return;
    try { await Duo.uploadBackground(file); Duo.toast('Background image saved.'); } catch (e) { Duo.toast(e.message); }
  });
}

function openCreateTabModal() {
  modal(`
    <div class="modal-head"><div><h3>Create New Tab</h3><p>Choose the smallest tracking model that matches the habit.</p></div><button class="modal-close" data-close>×</button></div>
    <label class="field-label">Name</label><input id="newTabName" class="input" placeholder="Reading, Language, Sleep…">
    <label class="field-label">Icon</label><input id="newTabIcon" class="input" maxlength="8" value="✦">
    <label class="field-label">Tracking type</label><select id="newTabType" class="select"><option>time log</option><option>checklist</option><option>notes</option><option>numeric counter</option></select>
    <div class="modal-actions"><button class="secondary-btn" data-close>Cancel</button><button id="saveNewTab" class="primary-btn">Create tab</button></div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#saveNewTab').addEventListener('click', async () => {
    try {
      const state = Duo.state || await Duo.loadState();
      const created = await Duo.api('/api/custom-tabs', { method:'POST', body:JSON.stringify({ name:root.querySelector('#newTabName').value, icon:root.querySelector('#newTabIcon').value, tracking_type:root.querySelector('#newTabType').value, created_by:state.players[0]?.id || null }) });
      closeModalRoot(); Duo.toast('Custom tab created.'); window.location.href = `/tabs/${created.tab.id}`;
    } catch (e) { Duo.toast(e.message); }
  });
}

function openCreateProjectModal() {
  modal(`
    <div class="modal-head"><div><h3>New project file</h3><p>Projects are shared. Ownership only changes the default owner.</p></div><button class="modal-close" data-close>×</button></div>
    <label class="field-label">Project name</label><input id="newProjectName" class="input" placeholder="Name the thing you want finished">
    <label class="field-label">Icon</label><input id="newProjectIcon" class="input" maxlength="8" value="🧪">
    <label class="field-label">Aim</label><textarea id="newProjectAim" class="textarea" placeholder="What should be true when this project is done?"></textarea>
    <label class="field-label">Owner</label><select id="newProjectOwner" class="select"></select>
    <div class="modal-actions"><button class="secondary-btn" data-close>Cancel</button><button id="saveNewProject" class="primary-btn">Create project</button></div>
  `);
  const root = document.getElementById('modalRoot');
  const players = Duo.state?.players || [];
  root.querySelector('#newProjectOwner').innerHTML = `<option value="">Shared</option>` + players.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#saveNewProject').addEventListener('click', async () => {
    try {
      const owner = root.querySelector('#newProjectOwner').value;
      const result = await Duo.api('/api/projects', { method:'POST', body:JSON.stringify({ name:root.querySelector('#newProjectName').value, icon:root.querySelector('#newProjectIcon').value, aim:root.querySelector('#newProjectAim').value, owner_id:owner ? Number(owner) : null }) });
      closeModalRoot(); Duo.toast('Project created.'); window.location.href = `/projects/${result.project.id}`;
    } catch (e) { Duo.toast(e.message); }
  });
}

(async function initDuo() {
  try { await Duo.loadState(); Duo.bindGlobal(); } catch (error) { Duo.toast(error.message); console.error(error); }
})();
window.Duo = Duo;
