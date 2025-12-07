import trafilatura
from typing import List, Dict, Any, Set, Optional
from urllib.parse import urlparse, urljoin
import asyncio
from bs4 import BeautifulSoup
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=5)

    def scrape_url(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single URL using Trafilatura.
        Returns dictionary with text, title, and metadata.
        """
        if not self._validate_url(url):
            logger.warning(f"Blocked unsafe or invalid URL: {url}")
            return None

        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                logger.warning(f"Failed to fetch URL: {url}")
                return None

            text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
            if not text:
                logger.warning(f"Failed to extract text from: {url}")
                return None
            
            return {
                "url": url,
                "text": text,
                "metadata": {
                    "source": url,
                    "type": "web_page"
                }
            }
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def _validate_url(self, url: str) -> bool:
        """
        Validate URL to prevent SSRF (Server Side Request Forgery).
        Blocks:
        - Localhost / Loopback
        - Private networks (10.x, 192.168.x, 172.16.x)
        - Link-local
        """
        import ipaddress
        import socket
        
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
                
            hostname = parsed.hostname
            if not hostname:
                return False
                
            # Allow public domains, block specific IPs
            try:
                # Resolve hostname to IP
                ip_list = socket.getaddrinfo(hostname, None)
                for item in ip_list:
                    ip_str = item[4][0]
                    ip_obj = ipaddress.ip_address(ip_str)
                    
                    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                        return False
                        
            except socket.gaierror:
                # Could not resolve, might be potentially unsafe or just broken
                return False
                
            return True
        except Exception:
            return False

    def download_file(self, url: str) -> Optional[bytes]:
        """Download a file from an URL."""
        import requests
        try:
            # Fake User-Agent to avoid blocking
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.content
            logger.warning(f"Download failed {url}: Status {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return None

    async def crawl_domain(self, start_url: str, max_pages: int = 10, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        Recursively crawl a domain starting from start_url.
        Uses BFS to visit pages.
        """
        domain = urlparse(start_url).netloc
        if not domain:
            raise ValueError(f"Invalid start URL: {start_url}")

        visited: Set[str] = set()
        queue: List[tuple[str, int]] = [(start_url, 0)] # (url, depth)
        results = []
        
        loop = asyncio.get_running_loop()
        
        while queue and len(results) < max_pages:
            current_url, depth = queue.pop(0)
            
            if current_url in visited:
                continue
            visited.add(current_url)
            
            logger.info(f"Scraping: {current_url} (Depth: {depth})")
            
            # Run blocking scrape in thread pool
            page_data = await loop.run_in_executor(self._executor, self.scrape_url, current_url)
            
            if page_data:
                page_data["metadata"]["depth"] = depth
                results.append(page_data)
                
                # Find links if depth < max_depth
                if depth < max_depth:
                    # Need to fetch HTML again or modify scrape_url to return HTML too.
                    # For efficiency, let's fetch HTML in scrape_url if we need links?
                    # Or just re-fetch/cache. Since trafilatura.fetch_url caches by default in memory? No.
                    # Let's keep it simple: we already fetched in scrape_url. 
                    # Optimization: scrape_url could return html content too if needed.
                    # But for now, let's just re-fetch for link extraction or refactor scrape_url.
                    # Refactoring scrape_url to be used here is better.
                    
                    # Actually, let's just do link extraction inside the executor if possible.
                    # But we need the HTML.
                    # Let's modify scrape_url to optionally return HTML or do it here.
                    # For now, to avoid breaking change, let's re-fetch (inefficient) or better:
                    # Let's assume scrape_url is enough for content.
                    # For crawling, we need links.
                    
                    # Optimization: Let's fetch once.
                    downloaded = await loop.run_in_executor(None, trafilatura.fetch_url, current_url)
                    if downloaded:
                        links = self._extract_links(downloaded, current_url, domain)
                        for link in links:
                            if link not in visited:
                                queue.append((link, depth + 1))
            
            # Be nice to the server
            await asyncio.sleep(0.5)
            
        return results

    def _extract_links(self, html: str, base_url: str, domain: str) -> List[str]:
        """Extract internal links from HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                try:
                    full_url = urljoin(base_url, href)
                    parsed = urlparse(full_url)
                    
                    # Filter: same domain, http/https
                    if parsed.netloc == domain and parsed.scheme in ('http', 'https'):
                        # Exclude common non-html extensions
                        if not any(parsed.path.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.zip', '.css', '.js']):
                            links.append(full_url)
                except Exception:
                    continue
            return links
        except Exception as e:
            logger.error(f"Error extracting links from {base_url}: {e}")
            return []
