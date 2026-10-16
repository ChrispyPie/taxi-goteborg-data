const MASTER_PASSWORD = 'taxi2026';

const drivers = {
  "15201": {
    name: "Christian",
    inkort: 18450,
    timmar: 42.5,
    mil: 312,
    perTimme: 434,
    perMil: 59.1,
    senastePass: [
      { start: "2026-10-15 18:00", slut: "2026-10-16 02:30", timmar: 8.5, belopp: 4120 },
      { start: "2026-10-14 17:45", slut: "2026-10-15 01:15", timmar: 7.5, belopp: 3680 }
    ]
  },
  "15202": {
    name: "Erik",
    inkort: 22100,
    timmar: 48,
    mil: 355,
    perTimme: 460,
    perMil: 62.3,
    senastePass: [
      { start: "2026-10-15 16:00", slut: "2026-10-16 04:00", timmar: 12, belopp: 5450 }
    ]
  },
  "15203": {
    name: "Anna",
    inkort: 15680,
    timmar: 36,
    mil: 268,
    perTimme: 436,
    perMil: 58.5,
    senastePass: [
      { start: "2026-10-15 19:30", slut: "2026-10-16 01:00", timmar: 5.5, belopp: 2890 }
    ]
  }
};

function checkPassword() {
  const input = document.getElementById('password').value;
  if (input === MASTER_PASSWORD) {
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app').style.display = 'block';
    renderDriver('15201');
  } else {
    document.getElementById('login-error').style.display = 'block';
  }
}

document.getElementById('password').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') checkPassword();
});

function formatSEK(num) {
  return new Intl.NumberFormat('sv-SE').format(num) + ' kr';
}

function renderDriver(driverId) {
  const d = drivers[driverId];
  if (!d) return;

  const html = `
    <div class="stats-grid">
      <div class="card">
        <h3>Inkört denna månad</h3>
        <div class="value">${formatSEK(d.inkort)}</div>
      </div>
      <div class="card">
        <h3>Per timme</h3>
        <div class="value">${d.perTimme}</div>
        <div class="unit">kr/h</div>
      </div>
      <div class="card">
        <h3>Per mil</h3>
        <div class="value">${d.perMil}</div>
        <div class="unit">kr/mil</div>
      </div>
      <div class="card">
        <h3>Arbetade timmar</h3>
        <div class="value">${d.timmar}</div>
        <div class="unit">h denna månad</div>
      </div>
    </div>

    <div class="section">
      <h2>Senaste pass</h2>
      <table>
        <thead>
          <tr><th>Start</th><th>Slut</th><th>Timmar</th><th>Belopp</th></tr>
        </thead>
        <tbody>
          ${d.senastePass.map(p => `
            <tr>
              <td>${p.start}</td>
              <td>${p.slut}</td>
              <td>${p.timmar}</td>
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
      <h2>Översikt åkeriet (demo)</h2>
      <div class="admin-overview">
        ${Object.entries(drivers).map(([id, d]) => `
          <div class="driver-card" onclick="document.getElementById('driver').value='${id}'; renderDriver('${id}')">
            <strong>${id} – ${d.name}</strong><br>
            Inkört: ${formatSEK(d.inkort)}<br>
            ${d.timmar} h – ${d.perTimme} kr/h
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