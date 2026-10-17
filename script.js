const MASTER_PASSWORD = 'taxi2026';
let data = {};
let currentDate = new Date();
let currentTab = localStorage.getItem('taxi_tab') || 'dag';
let currentDriver = localStorage.getItem('taxi_driver') || '';

const goals = { dag: 4000, vecka: 25000, manad: 100000 };
const typeMap = { '160': 'Kort', '283': 'Kredit', '163': 'Swish', '1': 'Kontant', '164': 'Uber', '161': 'Faktura', '185': 'Övrigt', '999': 'BOM' };
const weekdays = ['Sö', 'Må', 'Ti', 'On', 'To', 'Fr', 'Lö'];
const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec'];
const UBER_FEE = 0.26;

async function loadData() {
  try {
    const res = await fetch('data.json?t=' + Date.now());
    data = await res.json();
    const seenShifts = new Set();
    data.shifts = (data.shifts || []).filter(s => {
      const key = (s.passnr || '') + '|' + (s.forar || '710022');
      if (seenShifts.has(key)) return false;
      seenShifts.add(key);
      return true;
    });
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
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === currentTab));
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

function isCurrentPeriod() {
  const now = new Date();
  if (currentTab === 'dag') return isToday(currentDate);
  if (currentTab === 'vecka') return getWeekNumber(currentDate) === getWeekNumber(now) && currentDate.getFullYear() === now.getFullYear();
  return currentDate.getMonth() === now.getMonth() && currentDate.getFullYear() === now.getFullYear();
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

function getRemainingDays(date) {
  const today = new Date();
  today.setHours(0,0,0,0);
  const end = getMonthEnd(date);
  if (today > end) return 0;
  const diff = Math.ceil((end - today) / 86400000);
  return Math.max(0, diff);
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

function formatShiftDate(str) {
  const parts = (str || '').split(' ');
  if (!parts[0] || parts[0].length < 8) return '';
  const d = parts[0];
  return d.slice(6,8) + '/' + d.slice(4,6);
}

function render() {
  const isTodayNow = isToday(currentDate);
  const isCurrent = isCurrentPeriod();
  const dateEl = document.getElementById('current-date');
  const yy = String(currentDate.getFullYear()).slice(-2);
  
  if (currentTab === 'dag') {
    const wd = weekdays[currentDate.getDay()];
    const dd = String(currentDate.getDate()).padStart(2, '0');
    const mm = String(currentDate.getMonth() + 1).padStart(2, '0');
    dateEl.textContent = wd + ' ' + dd + '/' + mm + '-' + yy;
  } else if (currentTab === 'vecka') {
    const wn = getWeekNumber(currentDate);
    dateEl.textContent = 'V' + wn + ' -' + yy;
  } else {
    dateEl.textContent = months[currentDate.getMonth()] + ' -' + yy;
  }
  
  document.getElementById('today').classList.toggle('active', isTodayNow && currentTab === 'dag');
  document.getElementById('next').disabled = isCurrent;
  document.getElementById('next').style.opacity = isCurrent ? '0.3' : '1';

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

  shifts.sort((a, b) => (b.start || '').localeCompare(a.start || ''));

  let allTrips = [];
  let totalMinutes = 0;
  shifts.forEach(s => {
    allTrips = allTrips.concat(getTripsForShift(s));
    totalMinutes += parseTime(s.tid);
  });

  const trips = allTrips.filter(t => t.kredittyp !== '999');
  const antal = trips.length;
  const totalKm = trips.reduce((s, t) => s + parseAmount(t.kilometer), 0);
  const arbetad = formatTime(totalMinutes);
  const antalSkift = shifts.length;

  const kort = sumByType(trips, '160');
  const kredit = sumByType(trips, '283');
  const swish = sumByType(trips, '163');
  const kontant = sumByType(trips, '1');
  const uberGross = sumByType(trips, '164');
  const uberNetto = uberGross * (1 - UBER_FEE);
  const faktura = sumByType(trips, '161');
  const ovrigt = sumByType(trips, '185');
  const bom = sumByType(allTrips, '999');
  const dricks = trips.reduce((s, t) => s + parseAmount(t.dricks), 0);

  const inkort = kort + kredit + swish + kontant + uberNetto + faktura + ovrigt;
  const krPerKorning = antal ? Math.round(inkort / antal) : 0;
  const krPerMil = totalKm ? Math.round(inkort / (totalKm / 10)) : 0;
  const krPerTimme = totalMinutes ? Math.round(inkort / (totalMinutes / 60)) : 0;
  const goal = goals[currentTab] || 4000;
  const diff = inkort - goal;
  const inkortPerSkift = antalSkift ? Math.round(inkort / antalSkift) : 0;
  const remaining = Math.max(0, goal - inkort);
  const remainingDays = currentTab === 'manad' ? getRemainingDays(currentDate) : 0;
  const behovPerSkift = remainingDays > 0 ? Math.round(remaining / remainingDays) : 0;
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
      <div class="sub"><span>Behov/dag</span><span>${formatSEK(behovPerSkift)}</span></div>`;
  }

  let paymentSubs = `
    <div class="sub"><span>Kort</span><span>${formatSEK(kort)}</span></div>
    <div class="sub"><span>Kredit</span><span>${formatSEK(kredit)}</span></div>
    <div class="sub" style="opacity:0.5;"><span>Uber</span><span>${formatSEK(uberGross)}</span></div>
    <div class="sub"><span>Uber netto</span><span>${formatSEK(uberNetto)}</span></div>
    <div class="sub"><span>Kontant</span><span>${formatSEK(kontant)}</span></div>
    <div class="sub"><span>Swish</span><span>${formatSEK(swish)}</span></div>`;
  if (faktura > 0) paymentSubs += `<div class="sub"><span>Faktura</span><span>${formatSEK(faktura)}</span></div>`;
  if (ovrigt > 0) paymentSubs += `<div class="sub"><span>Övrigt</span><span>${formatSEK(ovrigt)}</span></div>`;
  if (bom > 0) paymentSubs += `<div class="sub" style="opacity:0.5;"><span>BOM</span><span>${formatSEK(bom)}</span></div>`;
  if (dricks > 0) paymentSubs += `<div class="sub" style="opacity:0.5;"><span>Dricks</span><span>${formatSEK(dricks)}</span></div>`;

  let html = `<div class="section">
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Arbetade timmar</span><span class="value">${arbetad}</span></div>
    ${timmarSubs}
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Körda km</span><span class="value">${totalKm.toFixed(1)} km</span></div>
    <div class="sub"><span>Kr/mil</span><span>${formatSEK(krPerMil)}</span></div>
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Antal körningar</span><span class="value">${antal} st</span></div>
    <div class="sub"><span>Kr/körning</span><span>${formatSEK(krPerKorning)}</span></div>
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">+</span><span class="label">Inkört</span><span class="value">${formatSEK(inkort)}</span></div>
    ${paymentSubs}
    <div class="stat-row" onclick="editGoal()"><span class="toggle"></span><span class="label">Mål</span><span class="value" style="border-bottom: 1px solid #cbd5e0; padding-bottom: 2px;">− ${formatSEK(goal)}</span></div>
    <div class="stat-row" onclick="toggle(this)"><span class="toggle">${currentTab !== 'dag' ? '+' : ''}</span><span class="label">Diff</span><span class="value" style="color:${diffColor}; font-weight:700;">${formatSEK(diff)}</span></div>
    ${diffSubs}
  </div>`;

  if (currentTab === 'dag') {
    if (allTrips.length) {
      html += `<div class="section">${allTrips.map(t => {
        const isBom = t.kredittyp === '999';
        return `<div class="stat-row" onclick="toggle(this)" style="${isBom ? 'opacity:0.6;' : ''}"><span class="toggle">+</span><span class="label">${t.kvittonr}${isBom ? ' (BOM)' : ''}</span><span class="value">${formatSEK(parseAmount(t.belopp))}</span></div>
        <div class="sub"><span>Start</span><span>${t.starttid || '00:00'} – zon ${t.startzon || '?'}</span></div>
        <div class="sub"><span>Slut</span><span>${t.sluttid || '00:00'} – zon ${t.slutzon || '?'}</span></div>
        <div class="sub"><span>Betalt</span><span>${formatSEK(parseAmount(t.belopp))}</span></div>
        <div class="sub"><span>Typ</span><span>${typeMap[t.kredittyp] || t.kredittyp || '?'}</span></div>
        <div class="sub"><span>Dricks</span><span>${formatSEK(parseAmount(t.dricks))}</span></div>`;
      }).join('')}</div>`;
    }
  } else {
    if (shifts.length) {
      html += `<div class="section">${shifts.map(s => {
        const shiftTrips = getTripsForShift(s);
        const shiftUber = shiftTrips.filter(t => t.kredittyp === '164').reduce((sum, t) => sum + parseAmount(t.belopp), 0);
        const shiftOther = shiftTrips.filter(t => t.kredittyp !== '999' && t.kredittyp !== '164').reduce((sum, t) => sum + parseAmount(t.belopp), 0);
        const shiftInkort = shiftOther + shiftUber * (1 - UBER_FEE);
        const dateLabel = formatShiftDate(s.start);
        const tripsHtml = shiftTrips.map(t => {
          const isBom = t.kredittyp === '999';
          return `<div class="sub shift-trip" onclick="toggleTrip(this)" style="${isBom ? 'opacity:0.6;' : ''}"><span class="toggle">+</span><span>${t.kvittonr}${isBom ? ' (BOM)' : ''}</span><span>${formatSEK(parseAmount(t.belopp))}</span></div>
          <div class="sub trip-detail"><span>Start</span><span>${t.starttid || '00:00'} – zon ${t.startzon || '?'}</span></div>
          <div class="sub trip-detail"><span>Slut</span><span>${t.sluttid || '00:00'} – zon ${t.slutzon || '?'}</span></div>
          <div class="sub trip-detail"><span>Typ</span><span>${typeMap[t.kredittyp] || t.kredittyp || '?'}</span></div>
          <div class="sub trip-detail"><span>Dricks</span><span>${formatSEK(parseAmount(t.dricks))}</span></div>`;
        }).join('');
        return `<div class="stat-row" onclick="toggleShift(this)"><span class="toggle">+</span><span class="label">${dateLabel} #${s.passnr}</span><span class="value">${formatSEK(shiftInkort)}</span></div>
        <div class="shift-content">${tripsHtml}</div>`;
      }).join('')}</div>`;
    }
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

function toggleShift(el) {
  const isOpen = el.classList.toggle('open');
  const icon = el.querySelector('.toggle');
  if (icon) icon.textContent = isOpen ? '−' : '+';
  const content = el.nextElementSibling;
  if (content && content.classList.contains('shift-content')) {
    content.style.display = isOpen ? 'block' : 'none';
  }
}

function toggleTrip(el) {
  event.stopPropagation();
  const isOpen = el.classList.toggle('open');
  const icon = el.querySelector('.toggle');
  if (icon) icon.textContent = isOpen ? '−' : '+';
  let next = el.nextElementSibling;
  while (next && next.classList.contains('trip-detail')) {
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
    localStorage.setItem('taxi_tab', currentTab);
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
  if (isCurrentPeriod()) return;
  if (currentTab === 'vecka') currentDate.setDate(currentDate.getDate() + 7);
  else if (currentTab === 'manad') currentDate.setMonth(currentDate.getMonth() + 1);
  else currentDate.setDate(currentDate.getDate() + 1);
  render();
};
document.getElementById('today').onclick = () => { currentDate = new Date(); render(); };