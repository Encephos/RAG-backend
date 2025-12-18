import requests
import time
import json
import sys

# --- KONFIGURATION ---
API_KEY = "fc-3a54a96e5228461e995b729864e5c715"  # Dein Key
START_URL = "https://www.seedfinder.eu/en/database/strains/autoflowering/"

def run_direct_crawl():
    if "fc-xxxx" in API_KEY:
        print("⚠️  Bitte trage deinen API Key ein!")
        return

    print(f"🚀 Starte Crawl via direkte API für: {START_URL}")

    create_url = "https://api.firecrawl.dev/v1/crawl"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Die korrekte Payload-Struktur für v1
    payload = {
        "url": START_URL,
        "limit": 20, 
        "scrapeOptions": {
            "formats": ["json"],
            # Wir helfen der KI, indem wir nur relevanten Content senden
            "includeTags": ["#content", ".strain-info", "table", ".content"],
            "jsonOptions": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "strain_name": { "type": "string" },
                        "breeder": { "type": "string" },
                        "full_lineage_tree": { 
                            "type": "string",
                            "description": "The COMPLETE genealogy/family tree. Capture nested hierarchy as text (e.g. '(A x B) x C'). Look for 'Genealogy / Family Tree'." 
                        },
                        "url": { "type": "string" }
                    },
                    "required": ["strain_name", "full_lineage_tree"]
                },
                "prompt": "Extract strain details. CRITICAL: Look for 'Genealogy / Family Tree'. Extract the ENTIRE known history as text."
            }
        },
        # WICHTIG: Das müssen gültige REGEX Patterns sein!
        "includePaths": [
            "/en/database/strains/autoflowering/.*", 
            "/en/strain-info/.*"
        ],
        "excludePaths": [
            "/de/.*", "/fr/.*", "/es/.*", 
            "/search/.*", "/gallery/.*", "/comments/.*", 
            ".*\\?sort=.*" 
        ]
    }

    try:
        response = requests.post(create_url, headers=headers, json=payload)
        
        # Falls Fehler, geben wir den genauen Grund aus
        if response.status_code != 200:
            print(f"❌ Fehler {response.status_code}: {response.text}")
            return

        data = response.json()
        job_id = data.get('id')
        print(f"✅ Job gestartet! ID: {job_id}")

    except Exception as e:
        print(f"❌ Kritischer Fehler: {e}")
        return

    # Polling Loop
    print("⏳ Warte auf Ergebnisse...")
    check_url = f"https://api.firecrawl.dev/v1/crawl/{job_id}"
    
    while True:
        try:
            status_res = requests.get(check_url, headers=headers)
            if status_res.status_code != 200:
                print(f" Fehler beim Check: {status_res.status_code}")
                time.sleep(5)
                continue
                
            status_data = status_res.json()
            status = status_data.get('status')
            completed = status_data.get('completed', 0)
            total = status_data.get('total', 0)
            
            sys.stdout.write(f"\r   Status: {status.upper()} - {completed}/{total} Seiten...")
            sys.stdout.flush()

            if status == 'completed':
                break
            elif status == 'failed':
                print("\n❌ Job failed!")
                return
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n🛑 Abgebrochen durch Nutzer.")
            return

    # Speichern
    print("\n💾 Speichere Daten...")
    clean_results = []
    if 'data' in status_data:
        for item in status_data['data']:
            # Manchmal ist das Ergebnis in 'extract', manchmal direkt im Objekt bei JSON Format
            extract = item.get('json') or item.get('extract')
            if extract:
                clean_results.append(extract)

    filename = "seedfinder_final.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(clean_results, f, indent=2, ensure_ascii=False)
        
    print(f"🎉 Fertig! {len(clean_results)} Einträge in '{filename}' gespeichert.")

if __name__ == "__main__":
    run_direct_crawl()