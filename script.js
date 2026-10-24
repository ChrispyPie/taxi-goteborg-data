// Huvudlösenordet ligger inte längre i koden – inloggning kontrolleras på servern (Supabase).
let drivers = {};

async function loadData() {
  try {
    const res = await fetch('data.json?t=' + Date.now());
    const data = await res.json();
    drivers = data.drivers || {};
    console.log('Data laddad:', Object.keys(drivers).length, 'förare');
    populateDriverSelect();
  } catch (e) {
    console.error('Kunde inte ladda data.json', e);
    drivers = {};
  }
}

function populateDriverSelect() {
  const select = document.getElementById('driver');
  select.innerHTML = '<option value="admin">Admin (översikt)</option>';
  Object.keys(drivers).sort().forEach(id => {
    const opt = document.createElement('option');
    opt.value = id;
    opt.textContent = `${id} – ${drivers[id].name || 'Förare'}`;
    select.appendChild(opt);
  });
}

function checkPassword() {
  const input = document.getElementById('password').value;
  if (false) { // gammal klient-inloggning avstängd
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app').style.display = 'block';
    loadData().then(() => {
      if (Object.keys(drivers).length > 0) {
        renderDriver(Object.keys(drivers)[0]);
      } else {
        document.getElementById('dashboard').innerHTML = '<p>Ingen data ännu. Kör scrapern först.</p>';
      }
    });
  } else {
    document.getElementById('login-error').style.display = 'block';
  }
}

document.getElementById('password').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') checkPassword();
});

function formatSEK(num) {
  return new Intl.NumberFormat('sv-SE').format(Math.round(num || 0)) + ' kr';
}

function renderDriver(driverId) {
  const d = drivers[driverId];
  if (!d) return;

  const html = `
    <div class="stats-grid">
      <div class="card">
        <h3>Inkört</h3>
        <div class="value">${formatSEK(d.inkort)}</div>
      </div>
      <div class="card">
        <h3>Per timme</h3>
        <div class="value">${d.perTimme || 0}</div>
        <div class="unit">kr/h</div>
      </div>
      <div class="card">
        <h3>Per mil</h3>
        <div class="value">${d.perMil || 0}</div>
        <div class="unit">kr/mil</div>
      </div>
      <div class="card">
        <h3>Arbetade timmar</h3>
        <div class="value">${d.timmar || 0}</div>
        <div class="unit">h</div>
      </div>
    </div>

    <div class="section">
      <h2>Senaste pass</h2>
      <table>
        <thead>
          <tr><th>Start</th><th>Slut</th><th>Timmar</th><th>Belopp</th></tr>
        </thead>
        <tbody>
          ${(d.senastePass || []).map(p => `
            <tr>
              <td>${p.start || '-'}</td>
              <td>${p.slut || '-'}</td>
              <td>${p.timmar || 0}</td>
              <td>${formatSEK(p.belopp)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  document.getElementById('dashboard').innerHTML = html;
}

function renderAdmin() {
  const html = `
    <div class="section">
      <h2>Översikt åkeriet</h2>
      <div class="admin-overview">
        ${Object.entries(drivers).map(([id, d]) => `
          <div class="driver-card" onclick="document.getElementById('driver').value='${id}'; renderDriver('${id}')">
            <strong>${id}</strong><br>
            Inkört: ${formatSEK(d.inkort)}<br>
            ${d.timmar || 0} h – ${d.perTimme || 0} kr/h
          </div>
        `).join('')}
      </div>
    </div>
  `;
  document.getElementById('dashboard').innerHTML = html;
}

document.getElementById('driver').addEventListener('change', (e) => {
  const val = e.target.value;
  if (val === 'admin') {
    renderAdmin();
  } else {
    renderDriver(val);
  }
});