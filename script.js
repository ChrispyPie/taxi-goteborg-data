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

function render() {
  // För tillfället: visa tom vy eftersom vi inte har nya resaposter efter senaste skift
  const html = `
    <div class="section">
      <h2>Pågående skift</h2>
      <div class="card">
        <p style="text-align:center; color:#718096; padding:2rem 0;">
          Inget pågående skift.<br>
          Tryck på Uppdatera när du har kört nya resor.
        </p>
      </div>
    </div>

    <div class="section">
      <h2>Historik</h2>
      <p style="color:#718096;">Avslutade skift visas här när Passrapport är inkopplad.</p>
    </div>
  `;
  document.getElementById('dashboard').innerHTML = html;
}