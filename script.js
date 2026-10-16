const MASTER_PASSWORD = 'taxi2026';
let data = {};

async function loadData() {
  try {
    const res = await fetch('data.json?t=' + Date.now());
    data = await res.json();
  } catch (e) {
    console.error(e);
    data = {};
  }
}

function checkPassword() {
  const input = document.getElementById('password').value;
  if (input === MASTER_PASSWORD) {
    document.getElementById('login-screen').style.display = 'none';
    document.getElementById('app').style.display = 'block';
    loadData().then(render);
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

function parseAmount(str) {
  if (!str) return 0;
  return parseFloat(str.replace(/\s/g, '').replace(',', '.')) || 0;
}

function render() {
  const trips = data.recent_trips || [];
  if (trips.length === 0) {
    document.getElementById('dashboard').innerHTML = '<p>Inga körningar ännu.</p>';
    return;
  }

  let total = 0;
  const rows = trips.map(t => {
    const c = t.raw || [];
    const belopp = parseAmount(c[7] || c[6]);
    total += belopp;
    const datum = c[8] || '';
    const tid = c[10] || '';
    const kvitto = c[4] || '';
    return `<tr><td>${datum} ${tid}</td><td>${kvitto}</td><td>${formatSEK(belopp)}</td></tr>`;
  }).join('');

  const html = `
    <div class="section">
      <h2>Pågående / senaste skift</h2>
      <div class="card" style="margin-bottom:1rem;">
        <h3>Inkört</h3>
        <div class="value">${formatSEK(total)}</div>
      </div>
      <table>
        <thead><tr><th>Tid</th><th>Kvitto</th><th>Belopp</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
  document.getElementById('dashboard').innerHTML = html;
}