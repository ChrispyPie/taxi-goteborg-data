const MASTER_PASSWORD = 'taxi2026';
let data = {};
let currentDate = new Date();
let currentTab = 'dag';

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

if (localStorage.getItem('taxi_logged_in') === '1') {
  showApp();
}

document.getElementById('password').addEventListener('keypress', e => {
  if (e.key === 'Enter') checkPassword();
});

function formatDate(d) {
  return d.toLocaleDateString('sv-SE', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function isToday(d) {
  return d.toDateString() === new Date().toDateString();
}

function render() {
  const todayBtn = document.getElementById('today');
  const isTodayNow = isToday(currentDate);
  document.getElementById('current-date').textContent = isTodayNow ? 'Idag' : formatDate(currentDate);
  todayBtn.classList.toggle('active', isTodayNow);

  let html = '';
  if (currentTab === 'dag') {
    if (isTodayNow) {
      html = `
        <div class="section">
          <h2>Pågående skift</h2>
          <div class="card"><p style="padding:1.5rem 0;">Inget pågående skift</p></div>
        </div>
      `;
    } else {
      html = `
        <div class="section">
          <h2>Skift ${formatDate(currentDate)}</h2>
          <div class="card"><p>Data från Passrapport visas här</p></div>
        </div>
      `;
    }
  } else {
    html = `<div class="section"><h2>${currentTab === 'vecka' ? 'Vecka' : 'Månad'}</h2><p>Kommer snart</p></div>`;
  }
  document.getElementById('dashboard').innerHTML = html;
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