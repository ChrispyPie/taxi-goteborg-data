const MASTER_PASSWORD = 'taxi2026';
let data = {};
let currentDate = new Date();
let currentTab = 'dag';

const goals = { dag: 4000, vecka: 25000, manad: 100000 };

async function loadData() {
  try {
    const res = await fetch('data.json?t=' + Date.now());
    data = await res.json();
  } catch (e) {
    data = {};
  }
}

function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  loadData().then(render);
}

function checkPassword() {
  if (document.getElementById('password').value === MASTER_PASSWORD) {
    localStorage.setItem('taxi_logged_in', '1');
    showApp();
  } else {
    document.getElementById('login-error').style.display = 'block';
  }
}

if (localStorage.getItem('taxi_logged_in') === '1') showApp();

document.getElementById('password').addEventListener('keypress', e => {
  if (e.key === 'Enter') checkPassword();
});

function formatDate(d) {
  return d.toLocaleDateString('sv-SE', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function isToday(d) {
  return d.toDateString() === new Date().toDateString();
}

function formatSEK(n) {
  return n ? new Intl.NumberFormat('sv-SE').format(Math.round(n)) + ' kr' : '—';
}

function parseAmount(str) {
  return parseFloat((str || '0').replace(/\s/g, '').replace(',', '.')) || 0;
}

function getTripsForDate(date) {
  const ymd = date.toISOString().slice(0,10).replace(/-/g, '');
  return (data.trips || []).filter(t => t.startdatum === ymd);
}

function render() {
  const isTodayNow = isToday(currentDate);
  document.getElementById('current-date').textContent = isTodayNow ? 'Idag' : formatDate(currentDate);
  document.getElementById('today').classList.toggle('active', isTodayNow);

  const trips = getTripsForDate(currentDate);
  const inkort = trips.reduce((s, t) => s + parseAmount(t.belopp), 0);
  const goal = goals[currentTab] || 4000;
  const diff = inkort - goal;

  const html = `
    <div class="section">
      <div class="stat-row"><span>Inkört</span><span>${formatSEK(inkort)}</span></div>
      <div class="stat-row"><span>Arbetade timmar</span><span>—</span></div>
      <div class="stat-row"><span>Körda km</span><span>—</span></div>
      <div class="stat-row" onclick="editGoal()"><span>Mål</span><span>${formatSEK(goal)}</span></div>
      <div class="stat-row"><span>Diff</span><span>${formatSEK(diff)}</span></div>
    </div>
    ${trips.length ? `<div class="section"><h3 style="padding:0.8rem 1.2rem;">Körningar</h3>${trips.map(t => `<div class="stat-row"><span>${t.starttid}</span><span>${formatSEK(parseAmount(t.belopp))}</span></div>`).join('')}</div>` : ''}
  `;
  document.getElementById('dashboard').innerHTML = html;
}

function editGoal() {
  const val = prompt('Nytt mål (kr):', goals[currentTab]);
  if (val && !isNaN(val)) {
    goals[currentTab] = parseInt(val);
    render();
  }
}

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    currentTab = btn.dataset.tab;
    render();
  });
});

document.getElementById('prev').onclick = () => { currentDate.setDate(currentDate.getDate() - 1); render(); };
document.getElementById('next').onclick = () => { currentDate.setDate(currentDate.getDate() + 1); render(); };
document.getElementById('today').onclick = () => { currentDate = new Date(); render(); };