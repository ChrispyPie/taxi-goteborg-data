#!/usr/bin/env python3
"""
STIG scraper – loggar in och laddar ner senaste rapportfiler.
Körs via GitHub Actions med secrets.
"""

import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

STIG_URL = "https://stig.taxinet.se"
USERNAME = os.environ.get("STIG_USERNAME", "15201")
PASSWORD = os.environ.get("STIG_PASSWORD", "")

def main():
    if not PASSWORD:
        print("STIG_PASSWORD saknas. Sätt den som secret.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print("Loggar in...")
        page.goto(f"{STIG_URL}/Login.aspx")
        page.wait_for_load_state("networkidle")

        # Välj bolag
        page.select_option("select", label="Taxi Göteborg")
        page.fill("input[name*='Username'], input[id*='Username']", USERNAME)
        page.fill("input[type='password']", PASSWORD)
        page.click("input[type='submit'], button:has-text('Logga in')")
        page.wait_for_load_state("networkidle")

        if "Login.aspx" in page.url:
            print("Inloggning misslyckades")
            browser.close()
            return

        print("Inloggad. Hämtar rapporter...")
        page.goto(f"{STIG_URL}/MedlemsRapporter.aspx")
        page.wait_for_load_state("networkidle")

        # Ladda ner första pass-filen som exempel
        sample_content = ""
        try:
            with page.expect_download() as download_info:
                # Klicka på nedladdningsknappen för pass-filen (tredje knappen ungefär)
                page.click("input[type='image'] >> nth=2")
            download = download_info.value
            path = download.path()
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                sample_content = f.read()[:2000]  # första 2000 tecken
            print("Nedladdning lyckades")
        except Exception as e:
            print(f"Nedladdning misslyckades: {e}")
            sample_content = "Kunde inte ladda ner fil"

        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "status": "scraper körd",
            "sample_file_preview": sample_content,
            "drivers": {}
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("data.json skapad")
        browser.close()

if __name__ == "__main__":
    main()