/* DaysHub 时光看板 — 前端逻辑 v2.1.0 */
let dashboardData = null;
let currentTab = 'all';
let searchResults = null;

// ========== 字符串转义工具 ==========
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// ========== 提示消息 (Toast) ==========
function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className = `toast ${type === 'error' ? 'toast-error' : ''} show`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.className = 'toast';
  }, 2300);
}

// ========== 密码与多用户认证（一年有效期） ==========
const TOKEN_KEY = 'dayshub_token';
const TOKEN_EXPIRY_KEY = 'dayshub_token_expiry';
const USER_INFO_KEY = 'dayshub_user_info';
const ONE_YEAR_MS = 365 * 24 * 60 * 60 * 1000;

let currentUser = null;

function getCurrentUser() {
  if (currentUser) return currentUser;
  try {
    const raw = localStorage.getItem(USER_INFO_KEY);
    if (raw) currentUser = JSON.parse(raw);
  } catch (e) {}
  return currentUser;
}

function saveCurrentUser(user) {
  currentUser = user;
  if (user) {
    localStorage.setItem(USER_INFO_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_INFO_KEY);
  }
}

function getToken() {
  const token = localStorage.getItem(TOKEN_KEY);
  const expiry = parseInt(localStorage.getItem(TOKEN_EXPIRY_KEY) || '0');
  if (!token) return null;
  if (Date.now() > expiry) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
    localStorage.removeItem(USER_INFO_KEY);
    currentUser = null;
    return null;
  }
  return token;
}

function saveAuth(token, user = null) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TOKEN_EXPIRY_KEY, String(Date.now() + ONE_YEAR_MS));
  if (user) saveCurrentUser(user);
}

function authHeaders(extra = {}) {
  const h = { ...extra };
  const t = getToken();
  if (t) h['Authorization'] = `Bearer ${t}`;
  return h;
}

function checkAuth() {
  const token = getToken();
  if (token) { showApp(); } else { showLogin(); }
}

function showLogin() {
  document.getElementById('loginPage').style.display = 'flex';
  document.getElementById('app').style.display = 'none';
  switchAuthMode('login');

  const uInput = document.getElementById('loginUsername');
  const pInput = document.getElementById('loginPassword');
  if (uInput) uInput.value = '';
  if (pInput) pInput.value = '';

  // 检查是否开放公开注册
  fetch('/api/system/public-info').then(r => r.json()).then(res => {
    const regLink = document.getElementById('registerSwitchLink');
    if (regLink) {
      regLink.style.display = res.allow_registration ? 'block' : 'none';
    }
  }).catch(() => {});
}

function switchAuthMode(mode) {
  const loginForm = document.getElementById('loginForm');
  const regForm = document.getElementById('registerForm');
  const title = document.getElementById('authCardTitle');
  const sub = document.getElementById('authCardSub');
  const loginErr = document.getElementById('loginError');
  const regErr = document.getElementById('regError');

  if (loginErr) loginErr.style.display = 'none';
  if (regErr) regErr.style.display = 'none';

  if (mode === 'register') {
    if (loginForm) loginForm.style.display = 'none';
    if (regForm) regForm.style.display = 'block';
    if (title) title.textContent = '注册账号';
    if (sub) sub.textContent = '创建您的个人时光看板';
    const regU = document.getElementById('regUsername');
    if (regU) regU.focus();
  } else {
    if (loginForm) loginForm.style.display = 'block';
    if (regForm) regForm.style.display = 'none';
    if (title) title.textContent = 'DaysHub';
    if (sub) sub.textContent = '农历 · 公历时光纪念看板';
    const loginU = document.getElementById('loginUsername');
    if (loginU) loginU.focus();
  }
}

async function doRegister(e) {
  e.preventDefault();
  const username = (document.getElementById('regUsername')?.value || '').trim();
  const display_name = (document.getElementById('regDisplayName')?.value || '').trim();
  const password = (document.getElementById('regPassword')?.value || '').trim();
  const password2 = (document.getElementById('regPassword2')?.value || '').trim();
  const errEl = document.getElementById('regError');
  errEl.style.display = 'none';

  if (!username || !password) {
    errEl.textContent = '用户名和密码不能为空';
    errEl.style.display = 'block';
    return;
  }
  if (password.length < 4) {
    errEl.textContent = '密码长度至少 4 位字符';
    errEl.style.display = 'block';
    return;
  }
  if (password !== password2) {
    errEl.textContent = '两次输入的密码不一致';
    errEl.style.display = 'block';
    return;
  }

  try {
    const resp = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, display_name, password }),
    });
    const data = await resp.json();
    if (resp.ok && data.ok) {
      saveAuth(data.token, data.user);
      showApp();
      loadTheme();
      loadDashboard();
      setupTabs();
      showToast(`🎉 欢迎加入 DaysHub，${data.user?.display_name || data.user?.username}！`);
    } else {
      errEl.textContent = data.error || '注册失败，请稍后重试';
      errEl.style.display = 'block';
    }
  } catch (err) {
    errEl.textContent = '网络请求失败';
    errEl.style.display = 'block';
  }
}

function showApp() {
  document.getElementById('loginPage').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  _updateUserUI();
}

function _updateUserUI() {
  const user = getCurrentUser();
  const isAdmin = user && user.role === 'admin';
  const adminGroup = document.getElementById('sidebarAdminGroup');
  if (adminGroup) {
    adminGroup.style.display = isAdmin ? 'flex' : 'none';
  }
  const userBtn = document.getElementById('subtabBtnUsers');
  if (userBtn) {
    userBtn.style.display = isAdmin ? 'flex' : 'none';
  }
  const logsBtn = document.getElementById('subtabBtnLogs');
  if (logsBtn) {
    logsBtn.style.display = 'flex';
  }
  const logModeToggle = document.getElementById('logModeToggle');
  if (logModeToggle) {
    logModeToggle.style.display = isAdmin ? 'inline-flex' : 'none';
  }
  const clearLogsBtn = document.getElementById('btnClearLogsBtn');
  if (clearLogsBtn) {
    clearLogsBtn.style.display = isAdmin ? 'inline-flex' : 'none';
  }
  if (!isAdmin && currentLogMode === 'runtime') {
    switchLogMode('audit');
  }
  const logTitle = document.getElementById('logTitleHeader');
  if (logTitle) {
    logTitle.textContent = isAdmin ? '操作审计日志' : '我的操作日志';
  }
  const backupStrategy = document.getElementById('backupStrategySection');
  if (backupStrategy) {
    backupStrategy.style.display = isAdmin ? 'block' : 'none';
  }
}

async function doLogin(e) {
  e.preventDefault();
  const username = (document.getElementById('loginUsername')?.value || '').trim();
  const password = document.getElementById('loginPassword').value.trim();
  const errEl = document.getElementById('loginError');
  errEl.style.display = 'none';
  try {
    const resp = await fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await resp.json();
    if (resp.ok && data.ok) {
      saveAuth(data.token || password, data.user);
      showApp();
      loadTheme();
      loadDashboard();
      setupTabs();
      showToast(`👋 欢迎回来，${data.user?.display_name || data.user?.username || '用户'}`);
    } else {
      errEl.textContent = data.error || '用户名或密码错误';
      errEl.style.display = 'block';
    }
  } catch (err) {
    errEl.textContent = '网络请求失败';
    errEl.style.display = 'block';
  }
}

function doLogout() {
  showConfirm('确认退出当前登录？', () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
    localStorage.removeItem(USER_INFO_KEY);
    currentUser = null;
    showLogin();
  });
}

async function apiFetch(url, options = {}) {
  const resp = await fetch(url, { ...options, headers: authHeaders(options.headers || {}) });
  if (resp.status === 401) { showLogin(); throw new Error('Unauthorized'); }
  return resp;
}

// ========== 确认弹窗 ==========
let _confirmCallback = null;
function showConfirm(text, callback) {
  document.getElementById('confirmText').textContent = text;
  document.getElementById('confirmModal').style.display = 'flex';
  _confirmCallback = callback;
}
function closeConfirm(confirmed) {
  document.getElementById('confirmModal').style.display = 'none';
  if (confirmed && _confirmCallback) _confirmCallback();
  _confirmCallback = null;
}

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
  checkAuth();
  if (getToken()) {
    loadTheme();
    loadDashboard();
    setupTabs();
  }
});

// ========== 看板数据 ==========
async function loadDashboard() {
  try {
    const resp = await apiFetch('/api/dashboard');
    dashboardData = await resp.json();
    renderHeader();
    renderHeroFocus();
    renderToday();
    renderTabs();
    refreshCategorySelects();
  } catch (e) { console.error('加载失败:', e); }
}

function getRemainingWeekends() {
  const now = new Date();
  const endOfYear = new Date(now.getFullYear(), 11, 31);
  let count = 0;
  const cur = new Date(now);
  while (cur <= endOfYear) {
    if (cur.getDay() === 0) count++;
    cur.setDate(cur.getDate() + 1);
  }
  return count;
}

// ========== 渲染头部与时间胶囊 ==========
function renderHeader() {
  const d = dashboardData;
  const lunar = d.lunar.chinese_str || '';
  const term = d.solar_term ? ` · 🌿 ${d.solar_term}` : '';
  document.getElementById('dateInfo').innerHTML =
    `${d.date} · ${lunar} · ${d.shengxiao}年${d.ganzhi}${term}`;
  const yp = d.year_progress;
  const mp = d.month_progress;
  const weekendsLeft = getRemainingWeekends();
  document.getElementById('progressBars').innerHTML = `
    <div class="progress-item">
      <div class="progress-label">
        <span>📊 年度时间胶囊</span>
        <span>已过 ${yp.passed}/${yp.total} 天 · 剩 ${yp.remaining} 天 (仅剩 ${weekendsLeft} 个周末) · ${yp.percent}%</span>
      </div>
      <div class="progress-bar"><div class="progress-fill" style="width:${yp.percent}%"></div></div>
    </div>
    <div class="progress-item">
      <div class="progress-label">
        <span>📅 本月进度</span>
        <span>${mp.passed}/${mp.total} 天 · 剩 ${mp.remaining} 天 · ${mp.percent}%</span>
      </div>
      <div class="progress-bar"><div class="progress-fill" style="width:${mp.percent}%"></div></div>
    </div>`;
}

// ========== 渲染今日焦点 Hero 卡片 ==========
function renderHeroFocus() {
  const section = document.getElementById('heroFocusSection');
  const card = document.getElementById('heroFocusCard');
  if (!section || !card || !dashboardData) return;

  const all = dashboardData.all_events || [];
  const todayEvs = dashboardData.today_events || [];

  let heroEv = null;
  let isTodayHero = false;

  if (todayEvs.length > 0) {
    heroEv = todayEvs[0];
    isTodayHero = true;
  } else {
    const upcoming = all.filter(e => e.event_type !== 'accumulate' && !e.is_today && (e.days_remaining !== null && e.days_remaining >= 0));
    upcoming.sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) return b.is_pinned ? 1 : -1;
      return (a.days_remaining ?? 9999) - (b.days_remaining ?? 9999);
    });
    if (upcoming.length > 0) {
      heroEv = upcoming[0];
    }
  }

  if (!heroEv) {
    section.style.display = 'none';
    return;
  }

  section.style.display = 'block';
  const tagText = isTodayHero ? '🎉 今日专属纪念' : (heroEv.days_remaining <= 3 ? '⚡ 紧迫倒计时' : (heroEv.is_pinned ? '📌 置顶焦点' : '🎯 焦点倒计时'));
  const subText = heroEv.lunar_str || (heroEv.next_date ? `公历 ${heroEv.next_date}` : heroEv.date);
  const noteStr = heroEv.note ? ` · 📝 ${heroEv.note}` : '';

  card.style.borderColor = heroEv.color || 'var(--accent)';
  card.onclick = () => editEvent(heroEv.id);

  card.innerHTML = `
    <div class="hero-focus-left">
      <span class="hero-focus-icon">${heroEv.icon || '⏳'}</span>
      <div class="hero-focus-info">
        <span class="hero-focus-tag" style="background:${heroEv.color || 'var(--accent)'};">${tagText}</span>
        <div class="hero-focus-title">${escapeHtml(heroEv.title)}</div>
        <div class="hero-focus-sub">${escapeHtml(subText)}${escapeHtml(noteStr)}</div>
      </div>
    </div>
    <div class="hero-focus-right">
      <div class="hero-focus-num" style="color:${heroEv.color || 'var(--accent)'};">${isTodayHero ? '今日' : heroEv.days_remaining}</div>
      <div class="hero-focus-unit">${isTodayHero ? '' : '天后'}</div>
    </div>
  `;
}

// ========== 渲染今日 ==========
function renderToday() {
  const events = dashboardData.today_events || [];
  const section = document.getElementById('todaySection');
  if (events.length === 0) { section.style.display = 'none'; return; }
  section.style.display = 'block';
  document.getElementById('todayEvents').innerHTML = events.map(ev => `
    <div class="today-card" style="border-color:${ev.color}" onclick="editEvent(${ev.id})">
      <span class="icon">${ev.icon}</span>
      <div class="info">
        <div class="title">${ev.title}</div>
        ${ev.note ? `<div class="note">📝 ${ev.note}</div>` : ''}
      </div>
      ${ev.age ? `<span class="age-badge" style="background:${ev.color}">第${ev.age}年</span>` : ''}
    </div>`).join('');
}

// ========== 排序 ==========
let sortState = {};
const SORT_OPTIONS = {
  countdown: [
    {field: 'days_remaining', label: '距离天数', order: 'asc'},
    {field: 'title', label: '名称', order: 'asc'},
    {field: 'next_date', label: '日期', order: 'asc'},
  ],
  recurring: [
    {field: 'days_remaining', label: '距离天数', order: 'asc'},
    {field: 'title', label: '名称', order: 'asc'},
    {field: 'next_date', label: '日期', order: 'asc'},
  ],
  accumulate: [
    {field: 'days_passed', label: '已过天数', order: 'desc'},
    {field: 'title', label: '名称', order: 'asc'},
    {field: 'date', label: '起始日期', order: 'asc'},
  ],
  all: [
    {field: 'days_remaining', label: '距离天数', order: 'asc'},
    {field: 'days_passed', label: '已过天数', order: 'desc'},
    {field: 'title', label: '名称', order: 'asc'},
    {field: 'date', label: '日期', order: 'asc'},
  ],
};

function renderSortBar(tabKey) {
  const bar = document.getElementById('sortBar-' + tabKey);
  if (!bar) return;
  const opts = SORT_OPTIONS[tabKey] || [];
  if (!opts.length) { bar.innerHTML = ''; return; }
  const cur = sortState[tabKey] || opts[0];
  let html = '<span class="sort-label">排序：</span>';
  for (const opt of opts) {
    const active = cur.field === opt.field;
    const arrow = active ? (cur.order === 'asc' ? ' ↑' : ' ↓') : '';
    const cls = active ? 'sort-btn active' : 'sort-btn';
    html += `<button class="${cls}" onclick="setSort('${tabKey}','${opt.field}','${opt.order}')">${opt.label}${arrow}</button>`;
  }
  bar.innerHTML = html;
}

function setSort(tabKey, field, defaultOrder) {
  const cur = sortState[tabKey];
  if (cur && cur.field === field) { cur.order = cur.order === 'asc' ? 'desc' : 'asc'; }
  else { sortState[tabKey] = {field, order: defaultOrder}; }
  renderSortBar(tabKey);
  if (tabKey === 'countdown') renderCountdown();
  else if (tabKey === 'recurring') renderRecurring();
  else if (tabKey === 'accumulate') renderAccumulate();
  else if (tabKey === 'all') renderAll();
}

function getSortedList(list, tabKey) {
  const cur = sortState[tabKey] || (SORT_OPTIONS[tabKey] && SORT_OPTIONS[tabKey][0]);
  if (!cur) return list;
  const sorted = [...list];
  sorted.sort((a, b) => {
    let va = a[cur.field], vb = b[cur.field];
    if (a.is_pinned && !b.is_pinned) return -1;
    if (!a.is_pinned && b.is_pinned) return 1;
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === 'string') return cur.order === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    return cur.order === 'asc' ? va - vb : vb - va;
  });
  return sorted;
}

// ========== 渲染标签 ==========
function renderTabs() {
  renderSortBar('countdown');
  renderSortBar('recurring');
  renderSortBar('accumulate');
  renderSortBar('all');
  renderCountdown();
  renderRecurring();
  renderAccumulate();
  renderAll();
  renderStats();
}

function renderCountdown() {
  const list = getSortedList(dashboardData.countdown || [], 'countdown');
  const container = document.getElementById('tab-countdown');
  if (!list.length) { container.innerHTML = '<div class="sort-bar" id="sortBar-countdown"></div><div class="empty">暂无倒数事件</div>'; renderSortBar('countdown'); return; }
  container.innerHTML = '<div class="sort-bar" id="sortBar-countdown"></div>' + list.map(ev => renderEventCard(ev)).join('');
  renderSortBar('countdown');
}

function renderRecurring() {
  const list = getSortedList(dashboardData.recurring || [], 'recurring');
  const container = document.getElementById('tab-recurring');
  if (!list.length) { container.innerHTML = '<div class="sort-bar" id="sortBar-recurring"></div><div class="empty">暂无循环事件</div>'; renderSortBar('recurring'); return; }
  container.innerHTML = '<div class="sort-bar" id="sortBar-recurring"></div>' + list.map(ev => renderEventCard(ev)).join('');
  renderSortBar('recurring');
}

function renderAccumulate() {
  const list = getSortedList(dashboardData.accumulate || [], 'accumulate');
  const container = document.getElementById('tab-accumulate');
  if (!list.length) { container.innerHTML = '<div class="sort-bar" id="sortBar-accumulate"></div><div class="empty">暂无累计事件</div>'; renderSortBar('accumulate'); return; }
  container.innerHTML = '<div class="sort-bar" id="sortBar-accumulate"></div>' + list.map(ev => renderAccumCard(ev)).join('');
  renderSortBar('accumulate');
}

function renderAll() {
  let list;
  if (searchResults) { list = searchResults; } else { list = dashboardData.all_events || []; }
  list = getSortedList(list, 'all');
  const container = document.getElementById('tab-all');
  if (!list.length) { container.innerHTML = '<div class="sort-bar" id="sortBar-all"></div><div class="empty">暂无事件</div>'; renderSortBar('all'); return; }
  container.innerHTML = '<div class="sort-bar" id="sortBar-all"></div>' + list.map(ev => {
    if (ev.event_type === 'accumulate') return renderAccumCard(ev);
    return renderEventCard(ev);
  }).join('');
  renderSortBar('all');
}

function renderEventCard(ev) {
  const days = ev.days_remaining;
  const isToday = ev.is_today;
  const sub = ev.lunar_str || (ev.next_date ? `公历 ${ev.next_date}` : ev.date);
  const ageStr = ev.age ? ` · 第${ev.age}年` : '';
  const pinIcon = ev.is_pinned ? '📌 ' : '';

  let urgencyCls = '';
  let urgencyBadge = '';
  if (!isToday && days !== null && days !== undefined) {
    if (days <= 3) {
      urgencyCls = 'urgent-pulse';
      urgencyBadge = `<span class="urgent-badge">⚡ 剩${days}天</span>`;
    } else if (days <= 15) {
      urgencyCls = 'impending';
    }
  }

  let daysHtml;
  if (isToday) { daysHtml = '<span class="ev-badge-today">🎉 今天</span>'; }
  else if (days !== null && days !== undefined) {
    daysHtml = `<div class="ev-days"><div class="ev-days-num" style="color:${ev.color}">${days}</div><div class="ev-days-unit">天后</div></div>`;
  } else { daysHtml = ''; }

  return `<div class="event-card ${ev.is_pinned ? 'pinned' : ''} ${urgencyCls}" style="border-color:${ev.color}" onclick="editEvent(${ev.id})">
    <div class="card-quick-actions" onclick="event.stopPropagation()">
      <button class="card-action-btn" title="${ev.is_pinned ? '取消置顶' : '置顶'}" onclick="quickTogglePin(${ev.id}, ${ev.is_pinned ? 0 : 1})">
        ${ev.is_pinned ? '📍' : '📌'}
      </button>
      <button class="card-action-btn" title="编辑" onclick="editEvent(${ev.id})">✏️</button>
      <button class="card-action-btn danger" title="删除" onclick="quickDeleteEvent(${ev.id}, '${escapeHtml(ev.title)}')">🗑️</button>
    </div>
    <span class="ev-icon">${ev.icon}</span>
    <div class="ev-info">
      <div class="ev-title">${pinIcon}${escapeHtml(ev.title)}${ageStr}${urgencyBadge}</div>
      <div class="ev-sub">${escapeHtml(sub)}${ev.note ? ' · 📝 ' + escapeHtml(ev.note) : ''}</div>
    </div>
    ${daysHtml}
  </div>`;
}

function renderAccumCard(ev) {
  const days = ev.days_passed || 0;
  const ms = ev.next_milestone;
  const msStr = ms ? ` · 下个里程碑: ${ms.milestone}天 (${ms.date})` : '';
  const pinIcon = ev.is_pinned ? '📌 ' : '';
  let msDots = '';
  if (ev.milestones) {
    msDots = `<div class="milestone-bar">${ev.milestones.map(m => {
      const cls = m.is_passed ? 'reached' : (m.milestone === ms?.milestone ? 'next' : '');
      return `<span class="milestone-dot ${cls}" title="${m.milestone}天"></span>`;
    }).join('')}</div>`;
  }
  return `<div class="event-card ${ev.is_pinned ? 'pinned' : ''}" style="border-color:${ev.color}" onclick="editEvent(${ev.id})">
    <div class="card-quick-actions" onclick="event.stopPropagation()">
      <button class="card-action-btn" title="${ev.is_pinned ? '取消置顶' : '置顶'}" onclick="quickTogglePin(${ev.id}, ${ev.is_pinned ? 0 : 1})">
        ${ev.is_pinned ? '📍' : '📌'}
      </button>
      <button class="card-action-btn" title="编辑" onclick="editEvent(${ev.id})">✏️</button>
      <button class="card-action-btn danger" title="删除" onclick="quickDeleteEvent(${ev.id}, '${escapeHtml(ev.title)}')">🗑️</button>
    </div>
    <span class="ev-icon">${ev.icon}</span>
    <div class="ev-info">
      <div class="ev-title">${pinIcon}${escapeHtml(ev.title)}</div>
      <div class="ev-sub">从 ${ev.date} 起${msStr}</div>
      ${msDots}
    </div>
    <div class="ev-days"><div class="ev-days-num" style="color:${ev.color}">${days}</div><div class="ev-days-unit">天已过</div></div>
  </div>`;
}

async function quickTogglePin(id, pinVal) {
  try {
    const resp = await apiFetch(`/api/events/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_pinned: pinVal })
    });
    if (resp.ok) {
      showToast(pinVal ? '📌 已置顶事件' : '已取消置顶');
      await loadDashboard();
    } else {
      showToast('操作失败', 'error');
    }
  } catch (e) {
    showToast('网络错误: ' + e.message, 'error');
  }
}

async function quickDeleteEvent(id, title) {
  showConfirm(`确定要删除事件 [${title}] 吗？`, async () => {
    try {
      const resp = await apiFetch(`/api/events/${id}`, { method: 'DELETE' });
      if (resp.ok) {
        showToast('✅ 事件已删除');
        await loadDashboard();
      } else {
        showToast('删除失败', 'error');
      }
    } catch (e) {
      showToast('网络错误: ' + e.message, 'error');
    }
  });
}

function renderStats() {
  const d = dashboardData;
  const all = d.all_events || [];
  const byCategory = {};
  all.forEach(e => { byCategory[e.category] = (byCategory[e.category] || 0) + 1; });
  const catHtml = Object.entries(byCategory).map(([k, v]) => {
    const cat = d.categories[k] || { name: k, icon: '📌', color: '#ccc' };
    return `<div class="stat-card" style="border-top:3px solid ${cat.color}">
      <div class="stat-val">${v}</div><div class="stat-label">${cat.icon} ${cat.name}</div></div>`;
  }).join('');
  document.getElementById('tab-stats').innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><div class="stat-val">${all.length}</div><div class="stat-label">总事件数</div></div>
      <div class="stat-card"><div class="stat-val">${(d.today_events||[]).length}</div><div class="stat-label">今日到期</div></div>
      <div class="stat-card"><div class="stat-val">${d.year_progress.percent}%</div><div class="stat-label">年度进度</div></div>
      <div class="stat-card"><div class="stat-val">${d.month_progress.percent}%</div><div class="stat-label">月度进度</div></div>
    </div>
    <h2 class="section-title" style="margin-top:16px">📂 分类统计</h2>
    <div class="stats-grid">${catHtml}</div>`;
}

// ========== 标签切换 ==========
function setupTabs() {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      currentTab = tab;
      document.getElementById('tab-' + tab).classList.add('active');
      if (searchResults) {
        searchResults = null;
        document.getElementById('searchInput').value = '';
        document.getElementById('searchCategory').value = '';
        renderTabs();
      }
    });
  });
}

// ========== 添加/编辑事件 ==========
function openAddModal() {
  document.getElementById('modalTitle').textContent = '添加事件';
  document.getElementById('eventForm').reset();
  document.getElementById('evId').value = '';
  document.getElementById('evType').value = 'countdown';
  document.getElementById('evCategory').value = 'family';
  document.getElementById('evDate').value = new Date().toISOString().slice(0, 10);
  document.getElementById('evAdvanceDays').value = 3;
  document.getElementById('lunarInputs').style.display = 'none';
  document.getElementById('evIsLunar').checked = false;
  document.getElementById('evIsLeap').checked = false;
  document.getElementById('btnDelete').style.display = 'none';
  document.getElementById('modalOverlay').style.display = 'flex';
  onSolarDateChange();
}

async function editEvent(id) {
  const resp = await apiFetch('/api/events');
  const events = await resp.json();
  const ev = events.find(e => e.id === id);
  if (!ev) return;
  document.getElementById('modalTitle').textContent = '编辑事件';
  document.getElementById('evId').value = ev.id;
  document.getElementById('evTitle').value = ev.title;
  document.getElementById('evType').value = ev.event_type;
  document.getElementById('evCategory').value = ev.category;
  document.getElementById('evDate').value = ev.date;
  document.getElementById('evNote').value = ev.note || '';
  document.getElementById('evPinned').checked = !!ev.is_pinned;
  document.getElementById('evAdvanceDays').value = ev.advance_days != null ? ev.advance_days : 3;
  if (ev.lunar_month && ev.lunar_day) {
    document.getElementById('evIsLunar').checked = true;
    document.getElementById('lunarInputs').style.display = 'block';
    document.getElementById('evLunarMonth').value = ev.lunar_month;
    document.getElementById('evLunarDay').value = ev.lunar_day;
    document.getElementById('evIsLeap').checked = !!ev.is_leap;
    onLunarChange();
  } else {
    document.getElementById('evIsLunar').checked = false;
    document.getElementById('evIsLeap').checked = false;
    document.getElementById('lunarInputs').style.display = 'none';
    onSolarDateChange();
  }
  document.getElementById('btnDelete').style.display = 'block';
  document.getElementById('modalOverlay').style.display = 'flex';
}

function closeModal() {
  document.getElementById('modalOverlay').style.display = 'none';
}

function toggleLunar() {
  const checked = document.getElementById('evIsLunar').checked;
  document.getElementById('lunarInputs').style.display = checked ? 'block' : 'none';
  if (checked) {
    document.getElementById('evType').value = 'recurring';
    onLunarChange();
  }
}

let _syncing = false;
async function onSolarDateChange() {
  if (_syncing) return;
  const dateStr = document.getElementById('evDate').value;
  if (!dateStr) return;
  try {
    const resp = await apiFetch(`/api/lunar/${dateStr}`);
    const data = await resp.json();
    if (data.lunar_month && data.lunar_day) {
      _syncing = true;
      document.getElementById('evLunarMonth').value = data.lunar_month;
      document.getElementById('evLunarDay').value = data.lunar_day;
      document.getElementById('evIsLeap').checked = !!data.is_leap;
      _syncing = false;
    }
  } catch (err) {}
}

async function onLunarChange() {
  if (_syncing) return;
  const month = parseInt(document.getElementById('evLunarMonth').value);
  const day = parseInt(document.getElementById('evLunarDay').value);
  const isLeap = document.getElementById('evIsLeap').checked;
  const dateStr = document.getElementById('evDate').value;
  if (!dateStr) return;
  const year = new Date(dateStr).getFullYear();
  try {
    const resp = await apiFetch(`/api/lunar_to_solar/${year}/${month}/${day}?is_leap=${isLeap ? 1 : 0}`);
    const data = await resp.json();
    if (data.date) {
      _syncing = true;
      document.getElementById('evDate').value = data.date;
      _syncing = false;
    }
  } catch (err) {}
}

async function saveEvent(e) {
  e.preventDefault();
  const id = document.getElementById('evId').value;
  const isLunar = document.getElementById('evIsLunar').checked;
  const data = {
    title: document.getElementById('evTitle').value,
    event_type: document.getElementById('evType').value,
    category: document.getElementById('evCategory').value,
    date: document.getElementById('evDate').value,
    note: document.getElementById('evNote').value,
    is_pinned: document.getElementById('evPinned').checked ? 1 : 0,
    advance_days: parseInt(document.getElementById('evAdvanceDays').value) || 3,
  };
  if (isLunar) {
    data.lunar_month = parseInt(document.getElementById('evLunarMonth').value);
    data.lunar_day = parseInt(document.getElementById('evLunarDay').value);
    data.is_leap = document.getElementById('evIsLeap').checked ? 1 : 0;
    data.is_recurring = 1;
    data.event_type = 'recurring';
    try {
      const isLeap = data.is_leap ? 1 : 0;
      const resp = await apiFetch(`/api/lunar_to_solar/${new Date(data.date).getFullYear()}/${data.lunar_month}/${data.lunar_day}?is_leap=${isLeap}`);
      const result = await resp.json();
      if (result.date) data.date = result.date;
    } catch (err) {}
  } else {
    // 显式置空农历字段，防止修改事件类型时旧农历数据残留
    data.lunar_month = null;
    data.lunar_day = null;
    data.is_leap = 0;
    data.is_recurring = (data.event_type === 'recurring' || data.event_type === 'monthly') ? 1 : 0;
  }
  const url = id ? `/api/events/${id}` : '/api/events';
  const method = id ? 'PUT' : 'POST';
  const resp = await apiFetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  if (resp.ok) {
    closeModal();
    showToast(id ? '✅ 事件已更新' : '✅ 事件创建成功');
    await loadDashboard();
  }
  else if (resp.status === 401) { showLogin(); }
  else { showToast('保存失败，请检查输入', 'error'); }
}

async function deleteCurrentEvent() {
  const id = document.getElementById('evId').value;
  if (!id) return;
  showConfirm('确认删除这个事件？\n删除后历史记录将保留，但事件不再显示。', async () => {
    const resp = await apiFetch(`/api/events/${id}`, { method: 'DELETE' });
    if (resp.ok) {
      closeModal();
      showToast('🗑️ 事件已删除');
      await loadDashboard();
    }
    else if (resp.status === 401) { showLogin(); }
  });
}

// ========== 日历订阅（支持弹窗与设置页内嵌） ==========
async function getIcalSubscriptionUrl() {
  try {
    const resp = await apiFetch('/api/settings/ical_token');
    const data = await resp.json();
    const token = data.token || '';
    return location.origin + '/api/calendar.ics?token=' + encodeURIComponent(token);
  } catch (err) {
    const token = getToken() || '';
    return location.origin + '/api/calendar.ics?token=' + encodeURIComponent(token);
  }
}

async function showCalendarModal() {
  const url = await getIcalSubscriptionUrl();
  const el = document.getElementById('calUrl');
  if (el) el.value = url;
  document.getElementById('calModal').style.display = 'flex';
}

function showCalendarFromBottom() {
  showSettings();
  switchSettingsTab('calendar');
}

async function loadSettingsCalendarView() {
  const url = await getIcalSubscriptionUrl();
  const el = document.getElementById('settingsCalUrl');
  if (el) el.value = url;
}

function copySettingsCalUrl() {
  const input = document.getElementById('settingsCalUrl');
  if (!input || !input.value) return;
  input.select(); input.setSelectionRange(0, 99999);
  if (navigator.clipboard) { navigator.clipboard.writeText(input.value); }
  showToast('✅ 日历订阅链接已复制到剪贴板');
}

async function resetSettingsCalToken() {
  showConfirm('确定要重置日历订阅 Token 吗？原订阅链接将立即失效，需要在日历 App 中更新。', async () => {
    try {
      const resp = await apiFetch('/api/settings/ical_token/reset', { method: 'POST' });
      const data = await resp.json();
      if (data.ok) {
        const url = location.origin + '/api/calendar.ics?token=' + encodeURIComponent(data.token);
        const el = document.getElementById('settingsCalUrl');
        if (el) el.value = url;
        const calModalInput = document.getElementById('calUrl');
        if (calModalInput) calModalInput.value = url;
        showToast('✅ 专属订阅 Token 已重置并更新');
      }
    } catch (err) {
      showToast('❌ 重置失败: ' + err.message);
    }
  });
}

async function resetCalToken() {
  showConfirm('确定要重置日历订阅 Token 吗？原订阅链接将立即失效，需要在日历 App 中更新。', async () => {
    try {
      const resp = await apiFetch('/api/settings/ical_token/reset', { method: 'POST' });
      const data = await resp.json();
      if (data.ok) {
        const url = location.origin + '/api/calendar.ics?token=' + encodeURIComponent(data.token);
        document.getElementById('calUrl').value = url;
        const el = document.getElementById('settingsCalUrl');
        if (el) el.value = url;
        showToast('✅ 订阅 Token 已重置并更新');
      }
    } catch (err) {
      showToast('❌ 重置失败: ' + err.message);
    }
  });
}

function copyCalUrl() {
  const input = document.getElementById('calUrl');
  input.select(); input.setSelectionRange(0, 99999);
  if (navigator.clipboard) { navigator.clipboard.writeText(input.value); }
  showToast('✅ 订阅链接已复制到剪贴板');
}

async function manualBackup() {
  try {
    showToast('正在创建全量备份...');
    const resp = await apiFetch('/api/backup', { method: 'POST' });
    const data = await resp.json();
    if (resp.ok && data.ok) {
      showToast('✅ 数据库与 JSON 快照已备份成功');
    } else {
      showToast(data.msg || '备份失败', 'error');
    }
  } catch (err) {
    showToast('备份请求失败', 'error');
  }
}

// ========== 导入导出 ==========
function exportData() {
  apiFetch('/api/export').then(r => r.json()).then(data => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `dayshub_export_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
  });
}

function importData(e) {
  const file = e.target.files[0];
  if (!file) return;
  showConfirm('⚠️ 导入将覆盖现有的全部事件数据，是否确认继续导入？', () => {
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        const resp = await apiFetch('/api/import?replace=true', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        });
        if (resp.ok) {
          const result = await resp.json();
          showConfirm(`✅ 导入完成: ${result.imported} 条`, () => {});
          await loadDashboard();
        } else if (resp.status === 401) { showLogin(); }
        else { showConfirm('导入失败，请检查文件格式', () => {}); }
      } catch (err) {
        showConfirm('文件解析失败，请确保是有效的 JSON', () => {});
      }
    };
    reader.readAsText(file);
  });
  // 重置 input 以允许再次选择相同文件
  e.target.value = '';
}

// ========== 设置页面 (多页面选项卡切换) ==========
function switchSettingsTab(tabName) {
  document.querySelectorAll('.settings-nav-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.subtab === tabName);
  });
  document.querySelectorAll('.settings-page').forEach(page => {
    page.classList.toggle('active', page.id === `subtab-${tabName}`);
  });
  const msgEl = document.getElementById('settingsMsg');
  if (msgEl) msgEl.style.display = 'none';

  if (tabName === 'calendar') {
    loadSettingsCalendarView();
  }
  if (tabName === 'category') {
    loadCategoryManageView();
  }
  if (tabName === 'users') {
    loadUserList();
  }
  if (tabName === 'logs') {
    loadSystemLogs(1);
  }
  if (tabName === 'backup') {
    loadBackupFileList();
  }
}

// ========== 备份文件列表加载与下载 ==========
async function loadBackupFileList() {
  const container = document.getElementById('backupFileListContainer');
  if (!container) return;
  const user = getCurrentUser();
  if (!user || user.role !== 'admin') {
    container.innerHTML = '<p class="modal-desc" style="color:var(--text-muted)">普通用户可直接使用上方 JSON 导入/导出备份</p>';
    return;
  }
  try {
    const resp = await apiFetch('/api/backup/list');
    const data = await resp.json();
    if (resp.ok && data.ok) {
      const files = data.files || [];
      if (!files.length) {
        container.innerHTML = '<p class="modal-desc">暂无备份快照文件</p>';
        return;
      }
      let html = '<div style="display:flex; flex-direction:column; gap:6px;">';
      for (const f of files) {
        const sizeKb = (f.size / 1024).toFixed(1);
        const token = getToken() || '';
        const dlUrl = `/api/backup/download/${encodeURIComponent(f.filename)}?token=${encodeURIComponent(token)}`;
        html += `
          <div style="display:flex; justify-content:space-between; align-items:center; padding:4px 0; border-bottom:1px solid var(--border);">
            <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:65%;">
              <b style="color:var(--text);">${f.filename}</b>
              <span style="color:var(--text-muted); font-size:11px; margin-left:6px;">${sizeKb} KB · ${f.created_at}</span>
            </div>
            <a href="${dlUrl}" target="_blank" download="${f.filename}" class="btn btn-secondary btn-sm" style="text-decoration:none; padding:3px 8px; font-size:11px;">
              ⬇ 下载
            </a>
          </div>
        `;
      }
      html += '</div>';
      container.innerHTML = html;
    } else {
      container.innerHTML = `<p class="modal-desc" style="color:var(--danger)">${data.msg || '无法加载备份列表'}</p>`;
    }
  } catch (err) {
    container.innerHTML = '<p class="modal-desc" style="color:var(--danger)">加载备份列表失败</p>';
  }
}

// ========== 用户管理 (管理员) ==========
async function loadUserList() {
  const container = document.getElementById('userListContainer');
  if (!container) return;

  // 1. 加载注册策略
  apiFetch('/api/admin/system').then(r => r.json()).then(res => {
    if (res.ok && res.allow_registration !== undefined) {
      const regBox = document.getElementById('allowRegistration');
      if (regBox) regBox.checked = res.allow_registration;
    }
  }).catch(() => {});

  // 2. 加载用户列表
  try {
    const resp = await apiFetch('/api/admin/users');
    const data = await resp.json();
    if (resp.ok && data.ok) {
      const users = data.users || [];
      if (!users.length) {
        container.innerHTML = '<p class="modal-desc">暂无用户记录</p>';
        return;
      }
      let html = `
        <table class="user-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>昵称</th>
              <th>角色</th>
              <th>状态</th>
              <th style="text-align:right;">操作</th>
            </tr>
          </thead>
          <tbody>
      `;
      for (const u of users) {
        const isAdmin = u.role === 'admin';
        const roleBadge = isAdmin ? '<span class="user-badge badge-admin">管理员</span>' : '<span class="user-badge badge-user">普通用户</span>';
        const statusBadge = u.is_active ?
          '<span class="status-dot status-active"></span>正常' :
          '<span class="status-dot status-inactive"></span>停用';
        const isSelf = currentUser && currentUser.id === u.id;
        const deleteBtn = (u.username === 'admin' || isSelf) ? '' : `<button class="user-action-btn btn-danger-text" onclick="deleteUserRow(${u.id}, '${u.username}')">删除</button>`;

        html += `
          <tr>
            <td><b>${u.username}</b></td>
            <td>${u.display_name || '-'}</td>
            <td>${roleBadge}</td>
            <td>${statusBadge}</td>
            <td style="text-align:right;">
              <button class="user-action-btn" onclick="openEditUserModal(${u.id})">编辑</button>
              ${deleteBtn}
            </td>
          </tr>
        `;
      }
      html += '</tbody></table>';
      container.innerHTML = html;
    } else {
      container.innerHTML = `<p class="modal-desc" style="color:var(--danger)">${data.error || '加载失败'}</p>`;
    }
  } catch (err) {
    container.innerHTML = '<p class="modal-desc" style="color:var(--danger)">加载用户列表网络错误</p>';
  }
}

async function toggleRegistrationSetting() {
  const allowed = document.getElementById('allowRegistration').checked;
  try {
    const resp = await apiFetch('/api/admin/system', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ allow_registration: allowed }),
    });
    const res = await resp.json();
    if (resp.ok && res.ok) {
      showToast(allowed ? '✅ 已开放访客自主注册' : '🔒 已关闭访客自主注册');
    } else {
      showToast(res.error || '设置失败', 'error');
    }
  } catch (err) {
    showToast('更新注册策略失败', 'error');
  }
}

let _editingUserId = null;
function openAddUserModal() {
  _editingUserId = null;
  document.getElementById('userModalTitle').textContent = '新增系统用户';
  document.getElementById('manageUserId').value = '';
  document.getElementById('manageUsername').value = '';
  document.getElementById('manageUsername').disabled = false;
  document.getElementById('manageDisplayName').value = '';
  document.getElementById('manageRole').value = 'user';
  document.getElementById('managePassword').value = '';
  document.getElementById('managePassword').required = true;
  document.getElementById('managePasswordLabel').textContent = '登录密码 *';
  document.getElementById('userModal').style.display = 'flex';
}

async function openEditUserModal(uid) {
  _editingUserId = uid;
  try {
    const resp = await apiFetch('/api/admin/users');
    const data = await resp.json();
    const user = (data.users || []).find(u => u.id === uid);
    if (!user) return;
    document.getElementById('userModalTitle').textContent = `编辑用户: ${user.username}`;
    document.getElementById('manageUserId').value = user.id;
    document.getElementById('manageUsername').value = user.username;
    document.getElementById('manageUsername').disabled = (user.username === 'admin');
    document.getElementById('manageDisplayName').value = user.display_name || '';
    document.getElementById('manageRole').value = user.role;
    document.getElementById('managePassword').value = '';
    document.getElementById('managePassword').required = false;
    document.getElementById('managePasswordLabel').textContent = '重置密码 (留空不修改)';
    document.getElementById('userModal').style.display = 'flex';
  } catch (err) {
    showToast('获取用户信息失败', 'error');
  }
}

async function saveUser(e) {
  e.preventDefault();
  const uid = document.getElementById('manageUserId').value;
  const username = document.getElementById('manageUsername').value.trim();
  const display_name = document.getElementById('manageDisplayName').value.trim();
  const role = document.getElementById('manageRole').value;
  const password = document.getElementById('managePassword').value;

  const data = { display_name, role };
  if (password) data.password = password;
  if (!uid) data.username = username;

  const url = uid ? `/api/admin/users/${uid}` : '/api/admin/users';
  const method = uid ? 'PUT' : 'POST';

  try {
    const resp = await apiFetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const res = await resp.json();
    if (resp.ok && res.ok) {
      document.getElementById('userModal').style.display = 'none';
      showToast(uid ? '✅ 用户信息已更新' : '✅ 新用户创建成功');
      loadUserList();
    } else {
      showToast(res.error || '保存失败', 'error');
    }
  } catch (err) {
    showToast('保存用户请求错误', 'error');
  }
}

function deleteUserRow(uid, username) {
  showConfirm(`确认彻底删除用户「${username}」？\n其关联的数据也将被清理。`, async () => {
    try {
      const resp = await apiFetch(`/api/admin/users/${uid}`, { method: 'DELETE' });
      const res = await resp.json();
      if (resp.ok && res.ok) {
        showToast(`✅ 用户 ${username} 已删除`);
        loadUserList();
      } else {
        showToast(res.error || '删除失败', 'error');
      }
    } catch (err) {
      showToast('删除请求失败', 'error');
    }
  });
}

function showSettings() {
  switchSettingsTab('push'); // 默认显示第一个选项卡

  // 加载推送设置
  apiFetch('/api/settings/push').then(r => r.json()).then(cfg => {
    document.getElementById('pushWecom').value = cfg.wecom_webhook || '';
    document.getElementById('pushSmtpHost').value = cfg.smtp_host || '';
    document.getElementById('pushSmtpPort').value = cfg.smtp_port || '';
    document.getElementById('pushSmtpUser').value = cfg.smtp_user || '';
    document.getElementById('pushSmtpPass').value = cfg.smtp_pass || '';
    document.getElementById('pushSmtpFrom').value = cfg.smtp_from || '';
    document.getElementById('pushSmtpTo').value = cfg.smtp_to || '';
    document.getElementById('pushSmtpSsl').checked = (cfg.smtp_ssl || 'true').toLowerCase() === 'true';
    document.getElementById('pushTgToken').value = cfg.tg_bot_token || '';
    document.getElementById('pushTgChatId').value = cfg.tg_chat_id || '';
  }).catch(() => {});

  // 加载备份配置
  apiFetch('/api/settings/backup').then(r => r.json()).then(res => {
    if (res.ok && res.config) {
      document.getElementById('backupEnabled').checked = !!res.config.backup_enabled;
      document.getElementById('backupTime').value = res.config.backup_time || '03:00';
      document.getElementById('backupCount').value = res.config.backup_count || 30;
      if (document.getElementById('backupType')) {
        document.getElementById('backupType').value = res.config.backup_type || 'both';
      }
    }
  }).catch(() => {});

  // 清空密码修改
  document.getElementById('oldPassword').value = '';
  document.getElementById('newPassword').value = '';
  document.getElementById('newPassword2').value = '';
  document.getElementById('settingsMsg').style.display = 'none';
  document.getElementById('settingsModal').style.display = 'flex';
}

async function saveBackupSettings() {
  const data = {
    backup_enabled: document.getElementById('backupEnabled').checked,
    backup_time: document.getElementById('backupTime').value.trim() || '03:00',
    backup_count: parseInt(document.getElementById('backupCount').value) || 30,
    backup_type: document.getElementById('backupType')?.value || 'both',
  };
  try {
    const resp = await apiFetch('/api/settings/backup', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (resp.ok) {
      showToast('✅ 自动备份策略已保存');
      showSettingsMsg('✅ 自动备份策略已保存', false);
    } else if (resp.status === 401) {
      showLogin();
    } else {
      showSettingsMsg('保存备份设置失败', true);
    }
  } catch (err) {
    showSettingsMsg('网络错误', true);
  }
}

function showSettingsMsg(msg, isError) {
  const el = document.getElementById('settingsMsg');
  el.textContent = msg;
  el.style.color = isError ? '#e74c3c' : '#27ae60';
  el.style.display = 'block';
}

async function savePushSettings() {
  const data = {
    wecom_webhook: document.getElementById('pushWecom').value.trim(),
    smtp_host: document.getElementById('pushSmtpHost').value.trim(),
    smtp_port: document.getElementById('pushSmtpPort').value.trim(),
    smtp_user: document.getElementById('pushSmtpUser').value.trim(),
    smtp_pass: document.getElementById('pushSmtpPass').value,
    smtp_from: document.getElementById('pushSmtpFrom').value.trim(),
    smtp_to: document.getElementById('pushSmtpTo').value.trim(),
    smtp_ssl: document.getElementById('pushSmtpSsl').checked ? 'true' : 'false',
    tg_bot_token: document.getElementById('pushTgToken').value.trim(),
    tg_chat_id: document.getElementById('pushTgChatId').value.trim(),
  };
  try {
    const resp = await apiFetch('/api/settings/push', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (resp.ok) { showSettingsMsg('✅ 推送设置已保存', false); }
    else if (resp.status === 401) { showLogin(); }
    else { showSettingsMsg('保存失败，请重试', true); }
  } catch (err) { showSettingsMsg('保存失败：网络错误', true); }
}

async function changePassword() {
  const oldPass = document.getElementById('oldPassword').value;
  const newPass = document.getElementById('newPassword').value;
  const newPass2 = document.getElementById('newPassword2').value;
  if (!oldPass || !newPass) { showSettingsMsg('请填写旧密码和新密码', true); return; }
  if (newPass !== newPass2) { showSettingsMsg('两次新密码不一致', true); return; }
  if (newPass.length < 4) { showSettingsMsg('新密码至少4位', true); return; }
  try {
    const resp = await apiFetch('/api/settings/password', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_password: oldPass, new_password: newPass }),
    });
    const data = await resp.json();
    if (resp.ok && data.ok) {
      showSettingsMsg('✅ 密码修改成功，请重新登录', false);
      // 更新本地token
      saveAuth(newPass);
      // 清空密码框
      document.getElementById('oldPassword').value = '';
      document.getElementById('newPassword').value = '';
      document.getElementById('newPassword2').value = '';
    } else {
      showSettingsMsg(data.error || '修改失败', true);
    }
  } catch (err) { showSettingsMsg('网络错误', true); }
}

async function testNotify() {
  showConfirm('确认测试推送？将向所有已配置的通道发送测试消息。', async () => {
    try {
      const resp = await apiFetch('/api/notify/test', { method: 'POST' });
      const data = await resp.json();
      if (resp.ok && data.ok) {
        showConfirm(data.msg, () => {});
      } else {
        // 推送失败也要显示错误详情
        showConfirm(data.msg || '推送失败', () => {});
      }
    } catch (err) {
      if (err.message !== 'Unauthorized') showConfirm('推送失败：网络错误', () => {});
    }
  });
}

// ========== 主题模式切换 (SVG 响应) ==========
const MOON_SVG = `<svg class="tool-btn-icon" viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
const SUN_SVG = `<svg class="tool-btn-icon" viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;

function _applyThemeUI(isDark) {
  const container = document.getElementById('themeIconContainer');
  const text = document.getElementById('themeText');
  if (container) container.innerHTML = isDark ? SUN_SVG : MOON_SVG;
  if (text) text.textContent = isDark ? '亮色' : '暗色';
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? '' : 'dark';
  if (next) { document.documentElement.setAttribute('data-theme', 'dark'); }
  else { document.documentElement.removeAttribute('data-theme'); }
  localStorage.setItem('dayshub-theme', next);
  _applyThemeUI(next === 'dark');
}

function loadTheme() {
  const saved = localStorage.getItem('dayshub-theme');
  const isDark = (saved === 'dark');
  if (isDark) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  _applyThemeUI(isDark);
}

// ========== 系统操作日志管理 ==========
let currentLogPage = 1;
let currentLogMode = 'audit';
const LOG_PAGE_SIZE = 25;

function switchLogMode(mode) {
  const user = getCurrentUser();
  if (mode === 'runtime' && (!user || user.role !== 'admin')) {
    showToast('⚠️ 运行日志仅管理员有权查看', 'error');
    mode = 'audit';
  }
  currentLogMode = mode;
  const btnAudit = document.getElementById('btnLogModeAudit');
  const btnRuntime = document.getElementById('btnLogModeRuntime');
  const viewAudit = document.getElementById('logAuditView');
  const viewRuntime = document.getElementById('logRuntimeView');

  if (mode === 'runtime') {
    if (btnAudit) { btnAudit.style.background = 'transparent'; btnAudit.style.color = 'var(--text-muted)'; }
    if (btnRuntime) { btnRuntime.style.background = 'var(--primary)'; btnRuntime.style.color = '#fff'; }
    if (viewAudit) viewAudit.style.display = 'none';
    if (viewRuntime) viewRuntime.style.display = 'block';
    loadRuntimeLogs();
  } else {
    if (btnAudit) { btnAudit.style.background = 'var(--primary)'; btnAudit.style.color = '#fff'; }
    if (btnRuntime) { btnRuntime.style.background = 'transparent'; btnRuntime.style.color = 'var(--text-muted)'; }
    if (viewAudit) viewAudit.style.display = 'block';
    if (viewRuntime) viewRuntime.style.display = 'none';
    loadSystemLogs(currentLogPage || 1);
  }
}

function refreshCurrentLogs() {
  if (currentLogMode === 'runtime') {
    loadRuntimeLogs();
  } else {
    loadSystemLogs(currentLogPage || 1);
  }
}

async function loadRuntimeLogs() {
  const container = document.getElementById('runtimeLogContainer');
  const infoEl = document.getElementById('runtimeLogFileInfo');
  if (!container) return;

  const lines = document.getElementById('runtimeLogLines')?.value || '100';
  container.textContent = '正在获取后端实时运行日志...';

  try {
    const resp = await apiFetch(`/api/admin/runtime_logs?lines=${lines}`);
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      container.textContent = `❌ 获取运行日志失败: ${data.error || '权限不足或未知错误'}`;
      return;
    }
    const logLines = data.lines || [];
    container.textContent = logLines.length ? logLines.join('\n') : '(当前日志文件为空)';
    if (infoEl) {
      const sizeKB = (data.file_size / 1024).toFixed(1);
      infoEl.textContent = `文件大小: ${sizeKB} KB | 当前展示: ${data.returned_count || 0} 行`;
    }
    // 自动滚动到最底部
    container.scrollTop = container.scrollHeight;
  } catch (err) {
    container.textContent = `❌ 请求运行日志异常: ${err.message}`;
  }
}

async function loadSystemLogs(page = 1) {
  const container = document.getElementById('logListContainer');
  const pagination = document.getElementById('logPagination');
  if (!container) return;

  const user = getCurrentUser();
  if (!user) {
    container.innerHTML = '<p class="modal-desc" style="color:var(--text-muted)">请先登录后查看日志</p>';
    if (pagination) pagination.innerHTML = '';
    return;
  }

  const isAdmin = user.role === 'admin';
  const urlEndpoint = isAdmin ? '/api/admin/logs' : '/api/user/logs';

  currentLogPage = page;
  const module = document.getElementById('logFilterModule')?.value || '';
  const keyword = (document.getElementById('logKeyword')?.value || '').trim();

  container.innerHTML = '<p class="modal-desc">加载中...</p>';

  try {
    const params = new URLSearchParams({
      limit: LOG_PAGE_SIZE,
      offset: (page - 1) * LOG_PAGE_SIZE,
    });
    if (module) params.append('module', module);
    if (keyword) params.append('keyword', keyword);

    const resp = await apiFetch(`${urlEndpoint}?${params.toString()}`);
    const data = await resp.json();
    if (!resp.ok || !data.ok) {
      container.innerHTML = `<p class="modal-desc" style="color:var(--danger)">加载失败: ${data.error || '未知错误'}</p>`;
      return;
    }

    const logs = data.logs || [];
    const total = data.total || 0;
    const totalPages = Math.ceil(total / LOG_PAGE_SIZE) || 1;

    if (!logs.length) {
      container.innerHTML = '<p class="modal-desc">暂无符合条件的操作日志记录</p>';
      if (pagination) pagination.innerHTML = '';
      return;
    }

    const moduleMap = {
      auth: '认证',
      event: '事件',
      user: '用户',
      system: '系统',
      category: '分类',
      widget: '组件'
    };

    let html = `
      <table class="log-table">
        <thead>
          <tr>
            <th style="width:130px;">时间</th>
            ${isAdmin ? '<th style="width:70px;">用户</th>' : ''}
            <th style="width:65px;">模块</th>
            <th>操作与详情</th>
            <th style="width:100px;">IP 地址</th>
            <th style="width:50px;">状态</th>
          </tr>
        </thead>
        <tbody>
    `;

    for (const log of logs) {
      const timeStr = (log.created_at || '').substring(5);
      const uStr = log.username ? escapeHtml(log.username) : '<span style="color:var(--text-muted)">系统</span>';
      const modStr = moduleMap[log.module] || escapeHtml(log.module || '其它');
      const isOk = log.status === 'ok';
      const statusBadge = isOk
        ? '<span class="user-badge badge-log-ok">成功</span>'
        : '<span class="user-badge badge-log-fail">失败</span>';
      const details = escapeHtml(log.details || log.action);
      const ipStr = escapeHtml(log.ip || '-');

      html += `
        <tr>
          <td style="color:var(--text-muted); font-size:11px; white-space:nowrap;">${escapeHtml(timeStr)}</td>
          ${isAdmin ? `<td><b>${uStr}</b></td>` : ''}
          <td><span class="user-badge badge-log-module">${modStr}</span></td>
          <td style="word-break:break-all;">${details}</td>
          <td style="color:var(--text-muted); font-size:11px; font-family:monospace;">${ipStr}</td>
          <td>${statusBadge}</td>
        </tr>
      `;
    }

    html += '</tbody></table>';
    container.innerHTML = html;

    if (pagination) {
      pagination.innerHTML = `
        <div>共 <b>${total}</b> 条日志 (第 ${page}/${totalPages} 页)</div>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-secondary btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="loadSystemLogs(${page - 1})">上一页</button>
          <button class="btn btn-secondary btn-sm" ${page >= totalPages ? 'disabled' : ''} onclick="loadSystemLogs(${page + 1})">下一页</button>
        </div>
      `;
    }
  } catch (err) {
    container.innerHTML = `<p class="modal-desc" style="color:var(--danger)">请求异常: ${err.message}</p>`;
  }
}

function clearSystemLogsPrompt() {
  showConfirm('确定要清理系统日志吗？\n建议保留近期记录或完全清空。', async () => {
    try {
      const resp = await apiFetch('/api/admin/logs', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days_to_keep: 0 })
      });
      const data = await resp.json();
      if (resp.ok && data.ok) {
        showSettingsMsg(`✅ ${data.msg || '日志已清理'}`, false);
        showToast(`✅ ${data.msg || '日志已清理'}`);
        loadSystemLogs(1);
      } else {
        showSettingsMsg(`❌ 清理失败: ${data.error || '未知错误'}`, true);
        showToast(`❌ 清理失败: ${data.error || '未知错误'}`, 'error');
      }
    } catch (e) {
      showSettingsMsg(`❌ 网络异常: ${e.message}`, true);
      showToast(`❌ 网络异常: ${e.message}`, 'error');
    }
  });
}

// ========== 分类管理功能与下拉框动态同步 ==========
function refreshCategorySelects() {
  const cats = (dashboardData && dashboardData.categories) ? dashboardData.categories : {};
  const searchSelect = document.getElementById('searchCategory');
  const evSelect = document.getElementById('evCategory');

  if (searchSelect) {
    const curVal = searchSelect.value;
    let html = '<option value="">全部分类</option>';
    for (const [slug, item] of Object.entries(cats)) {
      html += `<option value="${escapeHtml(slug)}">${item.icon || '📌'} ${escapeHtml(item.name)}</option>`;
    }
    searchSelect.innerHTML = html;
    if (cats[curVal]) searchSelect.value = curVal;
  }

  if (evSelect) {
    const curVal = evSelect.value;
    let html = '';
    for (const [slug, item] of Object.entries(cats)) {
      html += `<option value="${escapeHtml(slug)}">${item.icon || '📌'} ${escapeHtml(item.name)}</option>`;
    }
    evSelect.innerHTML = html;
    if (cats[curVal]) {
      evSelect.value = curVal;
    } else if (cats['family']) {
      evSelect.value = 'family';
    }
  }
}

async function loadCategoryManageView() {
  const container = document.getElementById('categoryManageContainer');
  if (!container) return;
  container.innerHTML = '<p class="modal-desc">加载分类列表中...</p>';
  try {
    const resp = await apiFetch('/api/categories');
    const cats = await resp.json();
    if (!resp.ok) {
      container.innerHTML = `<p class="modal-desc" style="color:var(--danger)">加载分类失败</p>`;
      return;
    }
    if (dashboardData) {
      dashboardData.categories = cats;
      refreshCategorySelects();
    }
    let html = '';
    for (const [slug, item] of Object.entries(cats)) {
      const isProtected = (slug === 'other');
      html += `
        <div class="cat-item-card">
          <div class="cat-badge-preview">
            <span style="font-size:18px;">${item.icon || '📌'}</span>
            <span style="color:${item.color || 'var(--text)'};">${escapeHtml(item.name)}</span>
            <span style="font-size:11px; color:var(--text-muted); font-family:monospace;">(${escapeHtml(slug)})</span>
          </div>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-secondary btn-sm" onclick="openEditCategoryModal('${escapeHtml(slug)}')">编辑</button>
            ${!isProtected ? `<button class="btn btn-danger btn-sm" onclick="deleteCategoryAction('${escapeHtml(slug)}')">删除</button>` : ''}
          </div>
        </div>
      `;
    }
    container.innerHTML = html || '<p class="modal-desc">暂无分类</p>';
  } catch (err) {
    container.innerHTML = `<p class="modal-desc" style="color:var(--danger)">加载异常: ${err.message}</p>`;
  }
}

function openAddCategoryModal() {
  document.getElementById('categoryModalTitle').textContent = '新增事件分类';
  const slugInput = document.getElementById('catSlug');
  slugInput.value = '';
  slugInput.readOnly = false;
  document.getElementById('catName').value = '';
  document.getElementById('catIcon').value = '📌';
  document.getElementById('catColor').value = '#6366f1';
  document.getElementById('categoryModal').style.display = 'flex';
}

function openEditCategoryModal(slug) {
  const cats = (dashboardData && dashboardData.categories) ? dashboardData.categories : {};
  const cat = cats[slug] || { name: slug, color: '#6366f1', icon: '📌' };
  document.getElementById('categoryModalTitle').textContent = `编辑分类: ${cat.name}`;
  const slugInput = document.getElementById('catSlug');
  slugInput.value = slug;
  slugInput.readOnly = true;
  document.getElementById('catName').value = cat.name;
  document.getElementById('catIcon').value = cat.icon || '📌';
  document.getElementById('catColor').value = cat.color || '#6366f1';
  document.getElementById('categoryModal').style.display = 'flex';
}

async function saveCategorySubmit(e) {
  e.preventDefault();
  const slug = document.getElementById('catSlug').value.trim().toLowerCase();
  const name = document.getElementById('catName').value.trim();
  const icon = document.getElementById('catIcon').value.trim() || '📌';
  const color = document.getElementById('catColor').value || '#6366f1';
  if (!slug || !name) {
    showToast('分类标识和名称不能为空', 'error');
    return;
  }
  try {
    const resp = await apiFetch('/api/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug, name, icon, color })
    });
    const res = await resp.json();
    if (resp.ok && res.ok) {
      showToast(res.msg || '分类已保存');
      document.getElementById('categoryModal').style.display = 'none';
      await loadCategoryManageView();
      await loadDashboard();
    } else {
      showToast(res.error || '保存失败', 'error');
    }
  } catch (err) {
    showToast('网络异常: ' + err.message, 'error');
  }
}

function deleteCategoryAction(slug) {
  showConfirm(`确定要删除分类 [${slug}] 吗？\n注意：如果仍有事件归属于此分类，将被系统拒绝。`, async () => {
    try {
      const resp = await apiFetch(`/api/categories/${encodeURIComponent(slug)}`, {
        method: 'DELETE'
      });
      const res = await resp.json();
      if (resp.ok && res.ok) {
        showToast(res.msg || '分类已删除');
        await loadCategoryManageView();
        await loadDashboard();
      } else {
        showToast(res.error || '删除失败', 'error');
      }
    } catch (err) {
      showToast('网络错误: ' + err.message, 'error');
    }
  });
}

