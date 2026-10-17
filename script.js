const MASTER_PASSWORD = 'taxi2026';
let data = {};
let currentDate = new Date();
let currentTab = 'dag';
let currentDriver = localStorage.getItem('taxi_driver') || '';

const goals = { dag: 4000, vecka: 25000, manad: 100000 };
const typeMap = { '160': 'Kort', '283': 'Kredit', '163': 'Swish', '1': 'Kontant', '164': 'Uber', '999': 'BOM' };

async function loadData() {
  try {
    const res = await fetch('data.json?t=' + Date.now());
    data = await res.json();
    // Dedupe shifts by passnr + forar
    const seenShifts = new Set();
    data.shifts = (data.shifts || []).filter(s => {
      const key = (s.passnr || '') + '|' + (s.forar || '710022');
      if (seenShifts.has(key)) return false;
      seenShifts.add(key);
      return true;
    });
    // Dedupe trips by kvittonr + forar
    const seenTrips = new Set();
    data.trips = (data.trips || []).filter(t => {
      const key = (t.kvittonr || '') + '|' + (t.forar || '710022');
      if (seenTrips.has(key)) return false;
      seenTrips.add(key);
      return true;
    });
  } catch (e) {
    data = {};
  }
}

function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  document.getElementById('driver-label').textContent = currentDriver;
  loadData().then(render);
}

function checkPassword() {
  const driverId = document.getElementById('driver-id').value.trim();
  const password = document.getElementById('password').value;
  if (driverId && password === MASTER_PASSWORD) {
    currentDriver = driverId;
    localStorage.setItem('taxi_logged_in', '1');
    localStorage.setItem('taxi_driver', driverId);
    showApp();
  } else {
    document.getElementById('login-error').style.display = 'block';
  }
}

function logout() {
  localStorage.removeItem('taxi_logged_in');
  localStorage.removeItem('taxi_driver');
  currentDriver = '';
  document.getElementById('login-screen').style.display = 'flex';
  document.getElementById('app').style.display = 'none';
  document.getElementById('driver-id').value = '';
  document.getElementById('password').value = '';
  document.getElementById('login-error').style.display = 'none';
}

if (localStorage.getItem('taxi_logged_in') === '1' && currentDriver) showApp();

document.getElementById('password').addEventListener('keypress', e => {
  if (e.key === 'Enter') checkPassword();
});
document.getElementById('driver-id').addEventListener('keypress', e => {
  if (e.key === 'Enter') document.getElementById('password').focus();
});

function formatDate(d) {
  return d.toLocaleDateString('sv-SE', { day: '2-digit', month: '2-digit' });
}

function getWeekNumber(d) {
  const date = new Date(d);
  date.setHours(0,0,0,0);
  date.setDate(date.getDate() + 3 - (date.getDay() + 6) % 7);
  const week1 = new Date(date.getFullYear(), 0, 4);
  return 1 + Math.round(((date - week1) / 86400000 - 3 + (week1.getDay() + 6) % 7) / 7);
}

function isToday(d) {
  return d.toDateString() === new Date().toDateString();
}

function formatSEK(n) {
  return new Intl.NumberFormat('sv-SE').format(Math.round(n || 0)) + ' kr';
}

function parseAmount(str) {
  return parseFloat((str || '0').replace(/\s/g, '').replace(',', '.')) || 0;
}

function parseShiftTime(str) {
  const parts = (str || '').split(' ');
  if (parts.length < 2) return null;
  const d = parts[0];
  const t = parts[1].replace(/ /g, '');
  return new Date(d.slice(0,4) + '-' + d.slice(4,6) + '-' + d.slice(6,8) + 'T' + t);
}

function getWeekStart(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  d.setHours(0,0,0,0);
  return d;
}

function getWeekEnd(date) {
  const start = getWeekStart(date);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  end.setHours(23,59,59,999);
  return end;
}

function getMonthStart(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function getMonthEnd(date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0, 23, 59, 59);
}

function getShiftsInRange(start, end) {
  return (data.shifts || []).filter(s => {
    const forar = s.forar || '710022';
    if (forar !== currentDriver) return false;
    const shiftStart = parseShiftTime(s.start);
    return shiftStart && shiftStart >= start && shiftStart <= end;
  });
}

function getShiftForDate(date) {
  const ymd = date.toISOString().slice(0,10).replace(/-/g, '');
  return (data.shifts || []).find(s => {
    const start = (s.start || '').replace(/\s/g, '');
    const forar = s.forar || '710022';
    return start.startsWith(ymd) && forar === currentDriver;
  });
}

function getTripsForShift(shift) {
  if (!shift) return [];
  const shiftStart = parseShiftTime(shift.start);
  const shiftEnd = parseShiftTime(shift.slut);
  if (!shiftStart || !shiftEnd) return [];

  return (data.trips || []).filter(t => {
    const forar = t.forar || '710022';
    if (forar !== currentDriver) return false;
    const tripDate = t.startdatum;
    const tripTime = t.starttid;
    if (!tripDate || !tripTime) return false;
    const tripDt = new Date(tripDate + 'T' + tripTime);
    return tripDt >= shiftStart && tripDt <= shiftEnd;
  });
}

function sumByType(trips, typeCode) {
  return trips.filter(t => t.kredittyp === typeCode).reduce((s, t) => s + parseAmount(t.belopp), 0);
}

function parseTime(tid) {
  if (!tid) return 0;
  const parts = tid.split(':');
  return parseInt(parts[0]) * 60 + parseInt(parts[1] || 0);
}

function formatTime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h + ':' + String(m).padStart(2, '0');
}

function render() {
  const isTodayNow = isToday(currentDate);
  const dateEl = document.getElementById('current-date');
  
  if (currentTab === 'dag') {
    dateEl.textContent = isTodayNow ? 'Idag' : formatDate(currentDate);
  } else if (currentTab === 'vecka') {
    const wn = getWeekNumber(currentDate);
    dateEl.textContent = 'Vecka ' + wn;
  } else {
    dateEl.textContent = currentDate.toLocaleDateString('sv-SE', { month: 'long', year: 'numeric' });
  }
  
  document.getElementById('today').classList.toggle('active', isTodayNow && currentTab === 'dag');

  if (data.last_updated) {
    const d = new Date(data.last_updated);
    document.getElementById('last-updated').textContent = 'Senast uppdaterad ' + d.toLocaleTimeString('sv-SE', { hour: '2-digit', minute: '2-digit' });
  }

  let shifts = [];
  if (currentTab === 'dag') {
    const s = getShiftForDate(currentDate);
    if (s) shifts = [s];
  } else if (currentTab === 'vecka') {
    shifts = getShiftsInRange(getWeekStart(currentDate), getWeekEnd(currentDate));
  } else {
    shifts = getShiftsInRange(getMonthStart(currentDate), getMonthEnd(currentDate));
  }

  let allTrips = [];
  let totalMinutes = 0;
  shifts.forEach(s => {
    allTrips = allTrips.concat(getTripsForShift(s));
    totalMinutes += parseTime(s.tid);
  });

  allTrips.sort((a, b) => {
    const da = (a.startdatum || '') + (a.starttid || '');
    const db = (b.startdatum || '') + (b.starttid || '');
    return db.localeCompare(da);
  });

  const trips = allTrips.filter(t => t.kredittyp !== '999');
  const inkort = trips.reduce((s, t) => s + parseAmount(t.belopp), 0);
  const antal = trips.length;
  const krPerKorning = antal ? Math.round(inkort / antal) : 0;
  const totalKm = trips.reduce((s, t) => s + parseAmount(t.kilometer), 0);
  const krPerMil = totalKm ? Math.round(inkort / (totalKm / 10)) : 0;
  const goal = goals[currentTab] || 4000;
  const diff = inkort - goal;
  const arbetad = formatTime(totalMinutes);
  const krPerTimme = totalMinutes ? Math.round(inkort / (totalMinutes / 60)) : 0;
  const antalSkift = shifts.length;

  const kort = sumByType(trips, '160');
  const kredit = sumByType(trips, '283');
  const swish = sumByType(trips, '163');
  const kontant = sumByType(trips, '1');
  const dricks = trips.reduce((s, t) => s + parseAmount(t.dricks), 0);

  const inkortPerSkift = antalSkift ? Math.round(inkort / antalSkift) : 0;
  const behovPerSkift = antalSkift ? Math.round(goal / antalSkift) : 0;
  const diffColor = diff >= 0 ? '#38a169' : '#e53e3e';

  let timmarSubs = '';
  if (currentTab === 'dag' && !isTodayNow && shifts.length) {
    const s = shifts[0];
    const startTid = (s.start || '').split(' ')[1] || '00:00';
    const slutTid = (s.slut || '').split(' ')[1] || '00:00';
    timmarSubs = `
      <div class="sub"><span>Start</span><span>${startTid}</span></div>
      <div class="sub"><span>Slut</span><span>${slutTid}</span></div>
      <div class="sub"><span>Kr/timme</span><span>${formatSEK(krPerTimme)}</span></div>`;
  } else if (currentTab !== 'dag') {
    timmarSubs = `
      <div class="sub"><span>Antal skift</span><span>${antalSkift} st</span></div>
      <div class="sub"><span>Kr/timme</span><span>${formatSEK(krPerTimme)}</span></div>`;
  }

  let diffSubs = '';
  if (currentTab !== 'dag') {
    diffSubs = `
      <div class="sub"><span>Inkört/skift</span><span>${formatSEK(inkortPerSkift)}</span></div>
      <div class="sub"><span>Behov/skift</span><span>${formatSEK(behovPerSkift)}</span></div>`;
  }

  let html = `<div class="section">
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Arbetade timmar</span><span class="value">${arbetad}</span></div>
    ${timmarSubs}
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Körda km</span><span class="value">${totalKm.toFixed(1)} km</span></div>
    <div class="sub"><span>Kr/mil</span><span>${formatSEK(krPerMil)}</span></div>
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Antal körningar</span><span class="value">${antal} st</span></div>
    <div class="sub"><span>Kr/körning</span><span>${formatSEK(krPerKorning)}</span></div>
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Inkört</span><span class="value">${formatSEK(inkort)}</span></div>
    <div class="sub"><span>Kort</span><span>${formatSEK(kort)}</span></div>
    <div class="sub"><span>Kredit</span><span>${formatSEK(kredit)}</span></div>
    <div class="sub"><span>Kontant</span><span>${formatSEK(kontant)}</span></div>
    <div class="sub"><span>Swish</span><span>${formatSEK(swish)}</span></div>
    <div class="sub"><span>Dricks</span><span>${formatSEK(dricks)}</span></div>
    <div class="stat-row" onclick="editGoal()"><span class="toggle"></span><span class="label">Mål</span><span class="value" style="border-bottom: 1px solid #cbd5e0; padding-bottom: 2px;">− ${formatSEK(goal)}</span></div>
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">${currentTab !== 'dag' ? '+' : ''}</span><span class="label">Diff</span><span class="value" style="color:${diffColor}; font-weight:700;">${formatSEK(diff)}</span></div>
    ${diffSubs}
  </div>`;

  if (allTrips.length) {
    html += `<div class="section">${allTrips.map(t => {
      const isBom = t.kredittyp === '999';
      const dateLabel = currentTab !== 'dag' && t.startdatum ? t.startdatum.slice(5) + ' ' : '';
      return `<div class="stat-row" onclick="toggle(this)" style="${isBom ? 'opacity:0.6;' : ''}"><span class="toggle">+</span><span class="label">${dateLabel}${t.kvittonr}${isBom ? ' (BOM)' : ''}</span><span class="value">${formatSEK(parseAmount(t.belopp))}</span></div>
      <div class="sub"><span>Start</span><span>${t.starttid || '00:00'} – zon ${t.startzon || '?'}</span></div>
      <div class="sub"><span>Slut</span><span>${t.sluttid || '00:00'} – zon ${t.slutzon || '?'}</span></div>
      <div class="sub"><span>Betalt</span><span>${formatSEK(parseAmount(t.belopp))}</span></div>
      <div class="sub"><span>Typ</span><span>${typeMap[t.kredittyp] || t.kredittyp || '?'}</span></div>
      <div class="sub"><span>Dricks</span><span>${formatSEK(parseAmount(t.dricks))}</span></div>`;
    }).join('')}</div>`;
  }

  document.getElementById('dashboard').innerHTML = html;
}

function toggle(el) {
  const isOpen = el.classList.toggle('open');
  const icon = el.querySelector('.toggle');
  if (icon && icon.textContent) icon.textContent = isOpen ? '−' : '+';
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

document.getElementById('prev').onclick = () => {
  if (currentTab === 'vecka') currentDate.setDate(currentDate.getDate() - 7);
  else if (currentTab === 'manad') currentDate.setMonth(currentDate.getMonth() - 1);
  else currentDate.setDate(currentDate.getDate() - 1);
  render();
};
document.getElementById('next').onclick = () => {
  if (currentTab === 'vecka') currentDate.setDate(currentDate.getDate() + 7);
  else if (currentTab === 'manad') currentDate.setMonth(currentDate.getMonth() + 1);
  else currentDate.setDate(currentDate.getDate() + 1);
  render();
};
document.getElementById('today').onclick = () => { currentDate = new Date(); render(); };