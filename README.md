# Taxi Göteborg Data

Intern demo-app för chaufförer att se sin kördata och statistik.

**Status:** Tidig prototyp med mock-data. Ingen riktig inloggning eller datahämtning ännu.

## Syfte
- Chaufförer ska kunna se inkört belopp, kr/timme, kr/mil, arbetade timmar etc.
- Admin (chefen) ska ha översikt och kunna klicka in på enskilda chaufförer.
- Data hämtas automatiskt från STIG (stig.taxinet.se) en gång i timmen (kommer senare).

## Nuvarande upplägg
- Enkel statisk webbplats med mock-data.
- Ingen lösenordsskydd just nu (demo-läge).
- Öppna `index.html` lokalt eller hosta på GitHub Pages / Vercel senare.

## Framtida
- Python-backend som scrapar STIG och sparar i databas.
- Riktig inloggning med förarnummer + lösenord.
- Anonyma topplistor.
- Zonstatistik.
- PWA.

**Endast för intern användning.**