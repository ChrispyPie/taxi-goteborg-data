#!/usr/bin/env python3
"""
Engångsscript: Uppdatera km för skift inom datumintervall.
"""

import os
import json
import re
from playwright.sync_api import sync_playwright

STIG_URL = "https://stig.taxinet.se"
USERNAME = os.environ.get("STIG_USERNAME", "15201")
PASSWORD = os.environ.get("STIG_PASSWORD", "")
FROM_DAY = int(os.environ.get("FROM_DAY", "1"))
TO_DAY = int(os.environ.get("TO_DAY", "18"))

def login(page):
    page.goto(f"{STIG_URL}/Login.aspx")
    page.wait_for_load_state("networkidle")
    page.select_option("select", label="Taxi Göteborg")
    page.fill("input[type='text']", USERNAME)
    page.fill("input[type='password']", PASSWORD)
    page.click("input[type='submit'], button, input[value*='Logga']")
    page.wait_for_load_state("networkidle")
    return "Login.aspx" not in page.url

def get_shift_data(page, passnr, forar, start_date):
    date_str = ""
    if start_date and len(start_date) >= 8:
        d = start_date.replace('\xa0', ' ').split()[0]
        if len(d) == 8:
            date_str = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")
    page.evaluate(f"""
        () => {{
            document.getElementById('MainContent_tbxForarId').value = '{forar}';
            document.getElementById('MainContent_tbxFromDat').value = '{date_str}';
            document.getElementById('MainContent_tbxTomDat').value = '{date_str}';
        }}
    """)
    page.click("input[value='Sök']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    result = page.evaluate(f"""
        () => {{
            const tables = document.querySelectorAll('table');
            for (const table of tables) {{
                const rows = table.querySelectorAll('tr');
                for (let i = 1; i < rows.length; i++) {{
                    const cells = rows[i].querySelectorAll('td');
                    const cellText = cells[8] ? cells[8].innerText.trim() : '';
                    if (cellText === '{passnr}' || cellText.includes('{passnr}')) {{
                        const start = cells[1] ? cells[1].innerText.trim() : '';
                        const slut = cells[2] ? cells[2].innerText.trim() : '';
                        const btn = rows[i].querySelector('input[type="image"]');
                        if (btn) {{ btn.click(); return {{ start, slut }}; }}
                    }}
                }}
            }}
            return null;
        }}
    """)
    if not result:
        return None

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    text = page.inner_text("body")
    match = re.search(r'Totalt antal km i pass:\s*([\d,]+)', text)
    km = match.group(1).replace(',', '.') if match else None
    return {"start": result.get("start"), "slut": result.get("slut"), "km": km}

def in_range(start_date):
    if not start_date:
        return False
    d = start_date.replace('\xa0', ' ').split()[0]
    if len(d) >= 8:
        day = int(d[6:8])
        return FROM_DAY <= day <= TO_DAY
    return False

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        return

    with open("data.json", "r") as f:
        data = json.load(f)

    shifts = data.get("shifts", [])
    to_update = [s for s in shifts if in_range(s.get("start", ""))]
    print(f"Skift dag {FROM_DAY}-{TO_DAY}: {len(to_update)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        updated = 0
        for s in to_update:
            passnr = s.get("passnr")
            forar = s.get("forar")
            start = s.get("start", "")
            if not passnr or not forar:
                continue
            result = get_shift_data(page, passnr, forar, start)
            if result and result.get("km"):
                s["km"] = result["km"]
                updated += 1
                print(f"  {passnr}: {result.get('km')} km")
            else:
                print(f"  {passnr}: misslyckades")

        data["shifts"] = shifts
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Uppdaterade {updated} skift")
        browser.close()

if __name__ == "__main__":
    main()