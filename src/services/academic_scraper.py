import requests
import logging
from typing import List, Dict, Any, Optional
from habanero import Crossref
from urllib.parse import quote

logger = logging.getLogger(__name__)

class AcademicSourceScraper:
    def __init__(self):
        self.crossref = Crossref()
        # Header ist wichtig, damit man nicht geblockt wird („Polite Pool“ bei Crossref)
        self.headers = {
            'User-Agent': 'NexusCouncilBot/1.0 (mailto:admin@example.com)'
        }

    def search_sources(self, query: str, limit: int = 5, category: str = "General") -> List[Dict[str, Any]]:
        """
        Hauptfunktion: Sucht parallel in verschiedenen hochwertigen Quellen.
        Gibt eine Liste von 'Source Candidates' zurück, die dein Ingest-System verarbeiten kann.
        """
        results = []
        
        print(f"🔍 Suche nach Quellen für '{category}': {query}...")

        # 1. Semantic Scholar (Fokus: Informatik, Biomedizin, Allgemeine Wissenschaft)
        # Sehr gut für Abstracts und Open Access PDF Links
        sem_scholar_results = self._fetch_semantic_scholar(query, limit)
        results.extend(sem_scholar_results)

        # 2. Crossref (Fokus: Spezifische Journals wie 'Frontiers in Plant Science')
        # Wir filtern hier spezifisch nach Cannabis-relevanten Journals für den Botanik-Experten
        if category.lower() in ["botanik", "botany", "production"]:
            # ISSN für Frontiers in Plant Science: 1664-462X
            frontiers_results = self._fetch_crossref(query, limit, filter_issn='1664-462X')
            results.extend(frontiers_results)
        else:
            # Allgemeine Crossref Suche für andere Kategorien
            crossref_results = self._fetch_crossref(query, limit)
            results.extend(crossref_results)

        print(f"✅ Insgesamt {len(results)} hochwertige Quellen gefunden.")
        return results

    def _fetch_semantic_scholar(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Holt Paper via Semantic Scholar Graph API.
        Vorteil: Liefert oft direkt den Link zum Open Access PDF.
        """
        base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
        # Wir fragen gezielt nach: Titel, Abstract, URL, PDF-Link, Jahr und Journal-Name
        fields = "title,abstract,url,year,venue,isOpenAccess,openAccessPdf"
        
        try:
            params = {"query": query, "limit": limit, "fields": fields}
            
            # Simple Retry Logic for 429
            import time
            retries = 3
            for i in range(retries):
                r = requests.get(base_url, params=params, headers=self.headers)
                if r.status_code == 200:
                    break
                if r.status_code == 429:
                    wait_time = (i + 1) * 2 # 2s, 4s, 6s
                    logger.warning(f"Semantic Scholar Rate Limit (429). Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                # Other errors
                break
            
            if r.status_code != 200:
                logger.error(f"Semantic Scholar Error after retries: {r.status_code}")
                return []

            data = r.json()
            hits = []
            
            for paper in data.get('data', []):
                # Nur Ergebnisse nutzen, die auch einen Abstract haben (sonst wertlos für RAG)
                if not paper.get('abstract'):
                    continue

                # Bevorzuge den direkten PDF-Link, falls vorhanden
                pdf_url = None
                if paper.get('openAccessPdf'):
                    pdf_url = paper.get('openAccessPdf', {}).get('url')

                hits.append({
                    "title": paper.get('title'),
                    "abstract": paper.get('abstract'), # Das ist oft schon genug Content!
                    "url": pdf_url if pdf_url else paper.get('url'), # URL für deinen Ingest
                    "source_api": "Semantic Scholar",
                    "metadata": {
                        "year": paper.get('year'),
                        "venue": paper.get('venue'),
                        "is_open_access": paper.get('isOpenAccess')
                    }
                })
            return hits

        except Exception as e:
            logger.error(f"Fehler bei Semantic Scholar Suche: {e}")
            return []

    def _fetch_crossref(self, query: str, limit: int, filter_issn: str = None) -> List[Dict[str, Any]]:
        """
        Holt Paper via Crossref (Habanero).
        Ideal um gezielt in spezifischen Journalen (über ISSN) zu suchen.
        """
        hits = []
        try:
            filters = {}
            if filter_issn:
                filters['issn'] = filter_issn

            # Crossref Suche
            res = self.crossref.works(query=query, filter=filters, limit=limit)
            
            for item in res['message']['items']:
                # Titel extrahieren
                title_list = item.get('title', [])
                title = title_list[0] if title_list else "Unbekannter Titel"
                
                # Abstract extrahieren (Crossref liefert das manchmal als XML-Fragment)
                abstract = item.get('abstract', '')
                if abstract:
                    # Simples Cleaning von XML Tags <jats:p> etc.
                    abstract = abstract.replace('<jats:p>', '').replace('</jats:p>', '').replace('<jx:p>', '')
                
                # Link extrahieren
                url = item.get('URL')
                
                # Wir nehmen es nur auf, wenn wir URL oder Abstract haben
                if url or abstract:
                    hits.append({
                        "title": title,
                        "abstract": abstract, # Kann leer sein bei Crossref
                        "url": url,
                        "source_api": "Crossref",
                        "metadata": {
                            "year": item.get('created', {}).get('date-parts', [[None]])[0][0],
                            "doi": item.get('DOI'),
                            "publisher": item.get('publisher')
                        }
                    })
            return hits

        except Exception as e:
            logger.error(f"Fehler bei Crossref Suche: {e}")
            return []
