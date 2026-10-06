/* Settings page — AI providers, players, tabs, data management, backups, danger zone */

// ─── AI Provider Slots ────────────────────────────────────────────────────────

function slotTemplate(row) {
  const status = row.last_status || 'untested';
  return `<article class="ai-slot">
    <div class="ai-slot-head">
      <strong>Slot ${row.slot} · ${escapeHtml(row.provider)}</strong>
      <span class="slot-status ${status === 'ok' ? 'ok' : status === 'failed' ? 'failed' : ''}">${escapeHtml(status)}</span>
    </div>
    <div class="ai-form">
      <input class="input" data-field="provider" value="${escapeHtml(row.provider)}" placeholder="Provider">
      <input class="input" data-field="model" value="${escapeHtml(row.model)}" placeholder="Model">
      <input class="input full" data-field="base_url" value="${escapeHtml(row.base_url)}" placeholder="https://api.example.com/v1">
      <div class="key-input-wrap full">
        <input class="input" data-field="key" type="password" placeholder="Leave blank to keep current key">
        <span class="masked">${escapeHtml(row.masked_key || 'no key')}</span>
      </div>
    </div>
    <div class="ai-actions">
      <label class="tag"><input type="checkbox" data-field="enabled" ${row.enabled ? 'checked' : ''}> enabled</label>
      <button class="secondary-btn save-ai" data-slot="${row.slot}">Save</button>
      <button class="primary-btn test-ai" data-slot="${row.slot}">Test</button>
    </div>
    <div class="inline-result">${escapeHtml(row.last_error || '')}</div>
  </article>`;
}

async function loadAi() {
  const data = await Duo.api('/api/settings/ai');
  document.getElementById('aiSlots').innerHTML = data.slots.map(slotTemplate).join('');
  bindAi();
}

function bindAi() {
  document.querySelectorAll('.save-ai').forEach(btn => btn.addEventListener('click', async () => {
    const slot = btn.closest('.ai-slot');
    const payload = {};
    slot.querySelectorAll('[data-field]').forEach(el => payload[el.dataset.field] = el.type === 'checkbox' ? el.checked : el.value);
    try {
      await Duo.api(`/api/settings/ai/${btn.dataset.slot}`, {
        method: 'PUT',
        body: JSON.stringify({ provider: payload.provider, base_url: payload.base_url, model: payload.model, key: payload.key || null, enabled: Boolean(payload.enabled) })
      });
      Duo.toast(`AI slot ${btn.dataset.slot} saved.`);
      await loadAi();
    } catch (e) { Duo.toast(e.message); }
  }));

  document.querySelectorAll('.test-ai').forEach(btn => btn.addEventListener('click', async () => {
    try {
      const result = await Duo.api(`/api/settings/ai/${btn.dataset.slot}/test`, { method: 'POST' });
      Duo.toast(`Slot ${btn.dataset.slot}: ${result.message}`);
      await loadAi();
    } catch (e) { Duo.toast(e.message); }
  }));
}

document.getElementById('failoverTest')?.addEventListener('click', async () => {
  const node = document.getElementById('failoverResult');
  node.textContent = 'Running simulated failover…';
  try {
    const result = await Duo.api('/api/settings/ai/test-failover', { method: 'POST' });
    node.textContent = result.ok
      ? `Failover path OK. First enabled slot was simulated as failed; request reached slot ${result.used_slot}.`
      : `Failover failed: ${result.message}`;
    await loadAi();
  } catch (e) { node.textContent = e.message; }
});

// ─── Appearance ───────────────────────────────────────────────────────────────

document.querySelectorAll('[data-theme-value]').forEach(button => button.addEventListener('click', async () => {
  try {
    await Duo.setBackground(button.dataset.themeValue, 'gradient', 'aurora');
    document.querySelectorAll('[data-theme-value]').forEach(x => x.classList.toggle('active', x === button));
    Duo.toast('Theme saved.');
  } catch (e) { Duo.toast(e.message); }
}));

document.querySelectorAll('[data-bg]').forEach(button => button.addEventListener('click', async () => {
  const value = button.dataset.bg;
  if (value === 'solid') return;
  try {
    await Duo.setBackground(document.body.dataset.theme || 'glass', 'gradient', value);
    Duo.toast('Background saved.');
  } catch (e) { Duo.toast(e.message); }
}));

document.getElementById('solidBg')?.addEventListener('input', async event => {
  try { await Duo.setBackground(document.body.dataset.theme || 'glass', 'solid', event.target.value); } catch (e) { Duo.toast(e.message); }
});

document.getElementById('settingsBgUpload')?.addEventListener('change', async event => {
  const file = event.target.files?.[0];
  if (!file) return;
  try { await Duo.uploadBackground(file); Duo.toast('Background image saved.'); } catch (e) { Duo.toast(e.message); }
});

// ─── Players Management ───────────────────────────────────────────────────────

async function loadPlayers() {
  const state = Duo.state || await Duo.loadState();
  const container = document.getElementById('playersManagement');
  if (!container) return;
  if (!state.players.length) {
    container.innerHTML = '<div class="empty-state">No players found.</div>';
    return;
  }
  container.innerHTML = state.players.map(p => `
    <div class="player-management-row">
      <div class="player-mgmt-avatar">${p.avatar_path ? `<img src="${escapeHtml(p.avatar_path)}" alt="${escapeHtml(p.name)}">` : `<span>${escapeHtml(p.emoji)}</span>`}</div>
      <div class="player-mgmt-info">
        <span class="mono-label">PLAYER ${String(p.id).padStart(2,'0')}</span>
        <strong>${escapeHtml(p.name)}</strong>
        <span class="tag">${p.points || 0} XP all-time</span>
      </div>
      <div class="player-mgmt-actions">
        <button class="secondary-btn" data-action="rename-player" data-player-id="${p.id}" data-player-name="${escapeHtml(p.name)}">Rename</button>
        <button class="secondary-btn" data-action="reset-player-score" data-player-id="${p.id}" data-player-name="${escapeHtml(p.name)}">Reset Score</button>
      </div>
    </div>
  `).join('');

  container.querySelectorAll('[data-action="rename-player"]').forEach(btn => {
    btn.addEventListener('click', () => openRenamePlayerModal(btn.dataset.playerId, btn.dataset.playerName));
  });
  container.querySelectorAll('[data-action="reset-player-score"]').forEach(btn => {
    btn.addEventListener('click', () => confirmResetPlayerScore(btn.dataset.playerId, btn.dataset.playerName));
  });
}

function openRenamePlayerModal(playerId, currentName) {
  modal(`
    <div class="modal-head"><div><h3>Rename Player</h3><p>Enter a new name for this player.</p></div><button class="modal-close" data-close>×</button></div>
    <label class="field-label">New name</label>
    <input id="renamePlayerInput" class="input" value="${escapeHtml(currentName)}" maxlength="80">
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="primary-btn" id="confirmRenamePlayer">Rename</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#confirmRenamePlayer').addEventListener('click', async () => {
    const name = root.querySelector('#renamePlayerInput').value.trim();
    if (!name) return;
    try {
      await Duo.api(`/api/players/${playerId}`, { method: 'PATCH', body: JSON.stringify({ name, emoji: null }) });
      closeModalRoot();
      Duo.toast('Player renamed.');
      await Duo.loadState();
      await loadPlayers();
    } catch (e) { Duo.toast(e.message); }
  });
}

function confirmResetPlayerScore(playerId, playerName) {
  modal(`
    <div class="modal-head"><div><h3>Reset ${escapeHtml(playerName)}'s Score?</h3></div><button class="modal-close" data-close>×</button></div>
    <div class="confirm-body">
      <p>This will permanently reset all of <strong>${escapeHtml(playerName)}</strong>'s points and daily stats to zero.</p>
      <p>Study entries, activities, and other records will be kept.</p>
    </div>
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="danger-btn" id="confirmResetScore">Reset Score</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#confirmResetScore').addEventListener('click', async () => {
    try {
      await Duo.api(`/api/data/reset-player/${playerId}`, { method: 'POST' });
      closeModalRoot();
      Duo.toast(`${playerName}'s score has been reset.`);
      await Duo.loadState();
      await loadPlayers();
    } catch (e) { Duo.toast(e.message); }
  });
}

// ─── Custom Tabs Management ────────────────────────────────────────────────────

async function loadTabsManagement() {
  const state = Duo.state || await Duo.loadState();
  const container = document.getElementById('tabsManagement');
  if (!container) return;
  if (!state.custom_tabs || !state.custom_tabs.length) {
    container.innerHTML = '<div class="empty-state">No custom tabs yet. Create one above to get started.</div>';
    return;
  }
  container.innerHTML = state.custom_tabs.map(tab => `
    <div class="tab-management-row" data-tab-id="${tab.id}">
      <span class="tab-mgmt-icon">${escapeHtml(tab.icon)}</span>
      <div class="tab-mgmt-info">
        <strong>${escapeHtml(tab.name)}</strong>
        <span class="tag">${escapeHtml(tab.tracking_type)}</span>
      </div>
      <div class="tab-mgmt-actions">
        <a class="secondary-btn" href="/tabs/${tab.id}">Open ↗</a>
        <button class="secondary-btn" data-action="rename-tab" data-tab-id="${tab.id}" data-tab-name="${escapeHtml(tab.name)}" data-tab-icon="${escapeHtml(tab.icon)}">Rename</button>
        <button class="secondary-btn danger-text" data-action="delete-tab" data-tab-id="${tab.id}" data-tab-name="${escapeHtml(tab.name)}">Delete</button>
      </div>
    </div>
  `).join('');

  container.querySelectorAll('[data-action="rename-tab"]').forEach(btn => {
    btn.addEventListener('click', () => openRenameTabModal(btn.dataset.tabId, btn.dataset.tabName, btn.dataset.tabIcon));
  });
  container.querySelectorAll('[data-action="delete-tab"]').forEach(btn => {
    btn.addEventListener('click', () => confirmDeleteTab(btn.dataset.tabId, btn.dataset.tabName));
  });
}

function openRenameTabModal(tabId, currentName, currentIcon) {
  modal(`
    <div class="modal-head"><div><h3>Rename Tab</h3><p>Update the name and icon for this custom tab.</p></div><button class="modal-close" data-close>×</button></div>
    <label class="field-label">Name</label>
    <input id="renameTabName" class="input" value="${escapeHtml(currentName)}" maxlength="100">
    <label class="field-label">Icon</label>
    <input id="renameTabIcon" class="input" value="${escapeHtml(currentIcon)}" maxlength="8">
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="primary-btn" id="confirmRenameTab">Save Changes</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#confirmRenameTab').addEventListener('click', async () => {
    const name = root.querySelector('#renameTabName').value.trim();
    const icon = root.querySelector('#renameTabIcon').value.trim();
    if (!name) return;
    try {
      await Duo.api(`/api/custom-tabs/${tabId}`, { method: 'PATCH', body: JSON.stringify({ name, icon: icon || null }) });
      closeModalRoot();
      Duo.toast('Tab updated.');
      await Duo.loadState();
      await loadTabsManagement();
    } catch (e) { Duo.toast(e.message); }
  });
}

function confirmDeleteTab(tabId, tabName) {
  modal(`
    <div class="modal-head"><div><h3>Delete "${escapeHtml(tabName)}"?</h3></div><button class="modal-close" data-close>×</button></div>
    <div class="confirm-body warning-body">
      <p>This will permanently delete:</p>
      <ul>
        <li>Tab configuration</li>
        <li>All tab-specific progress entries</li>
        <li>All tab-specific records</li>
      </ul>
      <p>Other tabs, players, and application data will not be affected.</p>
    </div>
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="danger-btn" id="confirmDeleteTab">Delete Tab</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#confirmDeleteTab').addEventListener('click', async () => {
    try {
      await Duo.api(`/api/custom-tabs/${tabId}`, { method: 'DELETE' });
      closeModalRoot();
      Duo.toast(`"${tabName}" deleted.`);
      await Duo.loadState();
      await loadTabsManagement();
    } catch (e) { Duo.toast(e.message); }
  });
}

// ─── Data Management ──────────────────────────────────────────────────────────

document.getElementById('clearHistoryBtn')?.addEventListener('click', () => {
  modal(`
    <div class="modal-head"><div><h3>Clear History?</h3></div><button class="modal-close" data-close>×</button></div>
    <div class="confirm-body warning-body">
      <p>This will remove all historical activity records including:</p>
      <ul>
        <li>Study entries</li>
        <li>Fitness activity logs</li>
        <li>Custom tab entries</li>
        <li>Points events &amp; daily stats</li>
        <li>Project notes &amp; task completion state</li>
      </ul>
      <p><strong>Preserved:</strong> Players, custom tabs, projects structure, settings, AI configuration.</p>
    </div>
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="danger-btn" id="confirmClearHistory">Clear History</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#confirmClearHistory').addEventListener('click', async () => {
    try {
      await Duo.api('/api/data/clear-history', { method: 'POST' });
      closeModalRoot();
      Duo.toast('History cleared.');
      await Duo.loadState();
    } catch (e) { Duo.toast(e.message); }
  });
});

document.getElementById('resetScoresBtn')?.addEventListener('click', () => {
  modal(`
    <div class="modal-head"><div><h3>Reset All Scores?</h3></div><button class="modal-close" data-close>×</button></div>
    <div class="confirm-body warning-body">
      <p>This will reset all player points and daily stats to zero.</p>
      <p><strong>Preserved:</strong> Study entries, activity logs, players, tabs, settings, AI configuration.</p>
    </div>
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="danger-btn" id="confirmResetScores">Reset Scores</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#confirmResetScores').addEventListener('click', async () => {
    try {
      await Duo.api('/api/data/reset-scores', { method: 'POST' });
      closeModalRoot();
      Duo.toast('All scores reset to zero.');
      await Duo.loadState();
    } catch (e) { Duo.toast(e.message); }
  });
});

// ─── Backups ─────────────────────────────────────────────────────────────────

async function loadBackups() {
  const container = document.getElementById('backupsList');
  if (!container) return;
  try {
    const data = await Duo.api('/api/data/backups');
    if (!data.backups.length) {
      container.innerHTML = '<div class="empty-state">No backups available. Click "Create Backup" to make one.</div>';
      return;
    }
    container.innerHTML = data.backups.map(b => {
      const date = new Date(b.created_at);
      const dateStr = date.toLocaleString();
      const sizeStr = (b.size_bytes / 1024).toFixed(1) + ' KB';
      return `<div class="backup-row">
        <div class="backup-info">
          <strong>${escapeHtml(b.filename)}</strong>
          <span class="mono-label">${dateStr} · ${sizeStr}</span>
        </div>
        <div class="backup-actions">
          <button class="secondary-btn" data-action="restore-backup" data-filename="${escapeHtml(b.filename)}">Restore</button>
          <button class="secondary-btn danger-text" data-action="delete-backup" data-filename="${escapeHtml(b.filename)}">Delete</button>
        </div>
      </div>`;
    }).join('');

    container.querySelectorAll('[data-action="restore-backup"]').forEach(btn => {
      btn.addEventListener('click', () => confirmRestoreBackup(btn.dataset.filename));
    });
    container.querySelectorAll('[data-action="delete-backup"]').forEach(btn => {
      btn.addEventListener('click', () => confirmDeleteBackup(btn.dataset.filename));
    });
  } catch (e) {
    container.innerHTML = `<div class="empty-state">Unable to load backups: ${escapeHtml(e.message)}</div>`;
  }
}

document.getElementById('createBackupBtn')?.addEventListener('click', async () => {
  try {
    const result = await Duo.api('/api/data/backup', { method: 'POST' });
    Duo.toast(`Backup created: ${result.filename}`);
    await loadBackups();
  } catch (e) { Duo.toast(e.message); }
});

function confirmRestoreBackup(filename) {
  modal(`
    <div class="modal-head"><div><h3>Restore Backup?</h3></div><button class="modal-close" data-close>×</button></div>
    <div class="confirm-body warning-body">
      <p>Restoring <strong>${escapeHtml(filename)}</strong> will overwrite the current database.</p>
      <p>All data created since this backup was made will be lost.</p>
      <p>The application will need to be refreshed after restoring.</p>
    </div>
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="danger-btn" id="confirmRestore">Restore Backup</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#confirmRestore').addEventListener('click', async () => {
    try {
      await Duo.api(`/api/data/restore/${encodeURIComponent(filename)}`, { method: 'POST' });
      closeModalRoot();
      Duo.toast('Backup restored. Refreshing…');
      setTimeout(() => window.location.reload(), 1500);
    } catch (e) { Duo.toast(e.message); }
  });
}

function confirmDeleteBackup(filename) {
  modal(`
    <div class="modal-head"><div><h3>Delete Backup?</h3></div><button class="modal-close" data-close>×</button></div>
    <div class="confirm-body">
      <p>Permanently delete <strong>${escapeHtml(filename)}</strong>? This cannot be undone.</p>
    </div>
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="danger-btn" id="confirmDeleteBkup">Delete</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  root.querySelector('#confirmDeleteBkup').addEventListener('click', async () => {
    try {
      await Duo.api(`/api/data/backups/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      closeModalRoot();
      Duo.toast('Backup deleted.');
      await loadBackups();
    } catch (e) { Duo.toast(e.message); }
  });
}

// ─── Full Reset (Danger Zone) ─────────────────────────────────────────────────

document.getElementById('fullResetBtn')?.addEventListener('click', () => {
  modal(`
    <div class="modal-head"><div><h3 class="danger-text">⚠ Reset Duo Tracker?</h3><p>This is a destructive, irreversible operation.</p></div><button class="modal-close" data-close>×</button></div>
    <div class="confirm-body warning-body">
      <p>This will permanently delete:</p>
      <ul>
        <li>All scores and points history</li>
        <li>All study and fitness entries</li>
        <li>All custom tabs and their data</li>
        <li>All projects, tasks, and notes</li>
      </ul>
      <p><strong>A database backup will be created automatically before the reset.</strong></p>
      <p><strong>Preserved:</strong> Player names &amp; avatars, AI provider configuration, appearance settings.</p>
    </div>
    <label class="field-label danger-label">Type <strong>RESET</strong> to confirm</label>
    <input id="resetConfirmInput" class="input" placeholder="RESET" autocomplete="off">
    <div class="modal-actions">
      <button class="secondary-btn" data-close>Cancel</button>
      <button class="danger-btn" id="confirmFullReset" disabled>Reset Duo Tracker</button>
    </div>
  `);
  const root = document.getElementById('modalRoot');
  root.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', closeModalRoot));
  const input = root.querySelector('#resetConfirmInput');
  const confirmBtn = root.querySelector('#confirmFullReset');
  input.addEventListener('input', () => {
    confirmBtn.disabled = input.value !== 'RESET';
  });
  confirmBtn.addEventListener('click', async () => {
    if (input.value !== 'RESET') return;
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Resetting…';
    try {
      const result = await Duo.api('/api/data/reset-all', { method: 'POST', body: JSON.stringify({ confirmation: 'RESET' }) });
      closeModalRoot();
      const msg = result.backup_created
        ? `Reset complete. Backup saved as ${result.backup_created}.`
        : 'Reset complete.';
      Duo.toast(msg);
      await Duo.loadState();
      await loadPlayers();
      await loadTabsManagement();
      await loadBackups();
    } catch (e) {
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Reset Duo Tracker';
      Duo.toast(e.message);
    }
  });
});

// ─── Initialise ───────────────────────────────────────────────────────────────

(async function initSettings() {
  try { await loadAi(); } catch (e) { Duo.toast(e.message); }
  try { await loadPlayers(); } catch (e) { /* players already in state */ }
  try { await loadTabsManagement(); } catch (e) { /* tabs in state */ }
  try { await loadBackups(); } catch (e) { /* non-critical */ }
})();

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
