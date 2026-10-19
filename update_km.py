#!/usr/bin/env python3
"""
Engångsscript: Uppdatera km för befintliga skift.
Söker varje skift via passnr och hämtar km.
"""

import os
import json
import re
from playwright.sync_api import sync_playwright

STIG_URL = "https://stig.taxinet.se"
USERNAME = os.environ.get("STIG_USERNAME", "15201")
PASSWORD = os.environ.get("STIG_PASSWORD", "")

def login(page):
    page.goto(f"{STIG_URL}/Login.aspx")
    page.wait_for_load_state("networkidle")
    page.select_option("select", label="Taxi Göteborg")
    page.fill("input[type='text']", USERNAME)
    page.fill("input[type='password']", PASSWORD)
    page.click("input[type='submit'], button, input[value*='Logga']")
    page.wait_for_load_state("networkidle")
    return "Login.aspx" not in page.url

def get_km_for_shift(page, passnr, forar):
    """Sök specifikt skift och hämta km."""
    page.goto(f"{STIG_URL}/Passrapport.aspx")
    page.wait_for_load_state("networkidle")
    page.evaluate(f"""
        () => {{
            document.getElementById('MainContent_tbxForarId').value = '{forar}';
            document.getElementById('MainContent_tbxFromDat').value = '';
            document.getElementById('MainContent_tbxTomDat').value = '';
        }}
    """)
    page.click("input[value='Sök']")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Hitta raden med rätt passnr och klicka förstoringsglas
    result = page.evaluate(f"""
        () => {{
            const tables = document.querySelectorAll('table');
            for (const table of tables) {{
                const rows = table.querySelectorAll('tr');
                for (let i = 1; i < rows.length; i++) {{
                    const cells = rows[i].querySelectorAll('td');
                    if (cells.length > 8 && cells[8].innerText.trim() === '{passnr}') {{
                        const btn = rows[i].querySelector('input[type="image"]');
                        if (btn) {{ btn.click(); return true; }}
                    }}
                }}
            }}
            return false;
        }}
    """)
    if not result:
        return None

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    text = page.inner_text("body")
    match = re.search(r'Totalt antal km i pass:\s*([\d,]+)', text)
    if match:
        return match.group(1).replace(',', '.')
    return None

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas")
        return

    with open("data.json", "r") as f:
        data = json.load(f)

    shifts = data.get("shifts", [])
    missing = [s for s in shifts if not s.get("km") or s.get("km") == "0"]
    print(f"Skift utan km: {len(missing)} av {len(shifts)}")

    if not missing:
        print("Alla skift har km")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        if not login(page):
            print("Inloggning misslyckades")
            browser.close()
            return

        updated = 0
        for s in missing:
            passnr = s.get("passnr")
            forar = s.get("forar")
            if not passnr or not forar:
                continue
            km = get_km_for_shift(page, passnr, forar)
            if km:
                s["km"] = km
                updated += 1
                print(f"  {passnr}: {km} km")
            else:
                print(f"  {passnr}: misslyckades")

        data["shifts"] = shifts
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Uppdaterade {updated} skift")
        browser.close()

if __name__ == "__main__":
    main()