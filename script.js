const MASTER_PASSWORD = 'taxi2026';
let data = {};
let currentDate = new Date();
let currentTab = 'dag';

const goals = { dag: 4000, vecka: 25000, manad: 100000 };
const typeMap = { '160': 'Kort', '283': 'Kredit', '163': 'Swish', '1': 'Kontant', '164': 'Uber', '999': 'BOM' };

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

function getShiftForDate(date) {
  const ymd = date.toISOString().slice(0,10).replace(/-/g, '');
  return (data.shifts || []).find(s => (s.start || '').replace(/\s/g, '').startsWith(ymd));
}

function getTripsForShift(shift) {
  if (!shift) return [];
  const startDate = (shift.start || '').split(' ')[0];
  const endDate = (shift.slut || '').split(' ')[0];
  return (data.trips || []).filter(t => {
    const td = (t.startdatum || '').replace(/-/g, '');
    return td === startDate || td === endDate;
  });
}

function sumByType(trips, typeCode) {
  return trips.filter(t => t.kredittyp === typeCode && t.kredittyp !== '999').reduce((s, t) => s + parseAmount(t.belopp), 0);
}

function render() {
  const isTodayNow = isToday(currentDate);
  document.getElementById('current-date').textContent = isTodayNow ? 'Idag' : formatDate(currentDate);
  document.getElementById('today').classList.toggle('active', isTodayNow);

  if (data.last_updated) {
    const d = new Date(data.last_updated);
    document.getElementById('last-updated').textContent = 'Senast uppdaterad ' + d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
  }

  const shift = getShiftForDate(currentDate);
  const allTrips = getTripsForShift(shift);
  const trips = allTrips.filter(t => t.kredittyp !== '999');
  const bomTrips = allTrips.filter(t => t.kredittyp === '999');

  const inkort = trips.reduce((s, t) => s + parseAmount(t.belopp), 0);
  const antal = trips.length;
  const krPerKorning = antal ? Math.round(inkort / antal) : 0;
  const totalKm = trips.reduce((s, t) => s + parseAmount(t.kilometer), 0);
  const krPerMil = totalKm ? Math.round(inkort / (totalKm / 10)) : 0;
  const goal = goals[currentTab] || 4000;
  const diff = inkort - goal;

  const startTid = shift ? shift.start.split(' ')[1] : '—';
  const slutTid = shift ? shift.slut.split(' ')[1] : '—';
  const arbetad = shift ? shift.tid : '—';

  const kort = sumByType(trips, '160');
  const kredit = sumByType(trips, '283');
  const swish = sumByType(trips, '163');
  const kontant = sumByType(trips, '1');
  const dricks = trips.reduce((s, t) => s + parseAmount(t.dricks), 0);

  const tripList = allTrips.map(t => {
    const isBom = t.kredittyp === '999';
    return `
    <div class="stat-row" onclick="toggle(this)" style="${isBom ? 'opacity:0.5;' : ''}">
      <span class="toggle">+</span>
      <span class="label">${t.kvittonr}${isBom ? ' (BOM)' : ''}</span>
      <span class="value">${isBom ? '—' : formatSEK(parseAmount(t.belopp))}</span>
    </div>
    <div class="sub"><span>Start</span><span>${t.starttid} – zon ${t.startzon || '?'}</span></div>
    <div class="sub"><span>Slut</span><span>${t.sluttid} – zon ${t.slutzon || '?'}</span></div>
    <div class="sub"><span>Betalt</span><span>${isBom ? '—' : formatSEK(parseAmount(t.belopp))}</span></div>
    <div class="sub"><span>Typ</span><span>${typeMap[t.kredittyp] || t.kredittyp || '—'}</span></div>
    <div class="sub"><span>Dricks</span><span>${formatSEK(parseAmount(t.dricks))}</span></div>
  `;
  }).join('');

  const html = `
    <div class="section">
      <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Arbetade timmar</span><span class="value">${arbetad}</span></div>
      <div class="sub"><span>Start</span><span>${startTid}</span></div>
      <div class="sub"><span>Slut</span><span>${slutTid}</span></div>

      <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Körda km</span><span class="value">${totalKm ? totalKm.toFixed(1) : '—'}</span></div>
      <div class="sub"><span>Kr/mil</span><span>${formatSEK(krPerMil)}</span></div>

      <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Antal körningar</span><span class="value">${antal || '—'}</span></div>
      <div class="sub"><span>Kr/körning</span><span>${formatSEK(krPerKorning)}</span></div>

      <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Inkört</span><span class="value">${formatSEK(inkort)}</span></div>
      <div class="sub"><span>Kort</span><span>${formatSEK(kort)}</span></div>
      <div class="sub"><span>Kredit</span><span>${formatSEK(kredit)}</span></div>
      <div class="sub"><span>Kontant</span><span>${formatSEK(kontant)}</span></div>
      <div class="sub"><span>Swish</span><span>${formatSEK(swish)}</span></div>
      <div class="sub"><span>Dricks</span><span>${formatSEK(dricks)}</span></div>

      <div class="stat-row" onclick="editGoal()"><span class="toggle"></span><span class="label">Mål</span><span class="value">${formatSEK(goal)}</span></div>
      <div class="stat-row"><span class="toggle"></span><span class="label">Diff</span><span class="value">${formatSEK(diff)}</span></div>
    </div>

    ${allTrips.length ? `<div class="section">${tripList}</div>` : ''}
  `;
  document.getElementById('dashboard').innerHTML = html;
}

function toggle(el) {
  const isOpen = el.classList.toggle('open');
  const icon = el.querySelector('.toggle');
  if (icon) icon.textContent = isOpen ? '−' : '+';

  let next = el.nextElementSibling;
  while (next && next.classList.contains('sub')) {
    next.classList.toggle('visible', isOpen);
    next = next.nextElementSibling;
  }
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