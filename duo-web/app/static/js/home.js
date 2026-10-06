(async function homePage() {
  const render = async () => {
    const state = Duo.state || await Duo.loadState();
    const comparison = document.getElementById('homeComparison');
    if (!comparison || state.players.length < 2) return;
    const a = state.players[0], b = state.players[1];
    const metric = (label, av, bv, suffix = '', max = Math.max(av, bv, 1)) => `
      <div class="compare-item"><div class="label">${label}</div><div class="compare-value"><b>${av}${suffix}</b><span>${bv}${suffix}</span></div><div class="bar"><div class="fill" style="width:${Math.min(100, av/max*100)}%"></div></div><div class="bar"><div class="fill hot" style="width:${Math.min(100, bv/max*100)}%"></div></div></div>`;
    comparison.innerHTML = [
      metric(`${escapeHtml(a.name)} · STUDY`, a.study_minutes, b.study_minutes, 'm', Math.max(a.study_minutes, b.study_minutes, 300)),
      metric(`${escapeHtml(b.name)} · STUDY`, b.study_minutes, a.study_minutes, 'm', Math.max(a.study_minutes, b.study_minutes, 300)),
      metric(`${escapeHtml(a.name)} · WORKOUT`, a.workout_minutes, b.workout_minutes, 'm', Math.max(a.workout_minutes, b.workout_minutes, 90)),
      metric(`${escapeHtml(b.name)} · WORKOUT`, b.workout_minutes, a.workout_minutes, 'm', Math.max(a.workout_minutes, b.workout_minutes, 90)),
      metric(`${escapeHtml(a.name)} · POINTS`, a.today_points, b.today_points, ' XP', Math.max(a.today_points, b.today_points, 500)),
      metric(`${escapeHtml(b.name)} · POINTS`, b.today_points, a.today_points, ' XP', Math.max(a.today_points, b.today_points, 500)),
    ].join('');
    document.getElementById('homeBestStreak').textContent = Math.max(a.streak, b.streak);
    document.getElementById('educationMeta').textContent = `${a.study_minutes + b.study_minutes} min today`;
    document.getElementById('fitnessMeta').textContent = `${a.workout_minutes + b.workout_minutes} min today`;
    document.getElementById('projectMeta').textContent = `${state.projects.length} active`;
  };
  await render();

  // Reload after actions elsewhere so demo values remain visibly live.
  document.addEventListener('duo:data-changed', render);
})();

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
}
