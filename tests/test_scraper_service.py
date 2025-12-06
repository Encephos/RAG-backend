import pytest
from unittest.mock import MagicMock, patch
from src.services.scraper_service import ScraperService

class TestScraperService:
    
    @patch("src.services.scraper_service.trafilatura.fetch_url")
    @patch("src.services.scraper_service.trafilatura.extract")
    def test_scrape_url_success(self, mock_extract, mock_fetch):
        """Test successful URL scraping."""
        mock_fetch.return_value = "<html><body>Some content</body></html>"
        mock_extract.return_value = "Some content"
        
        service = ScraperService()
        result = service.scrape_url("http://example.com")
        
        assert result is not None
        assert result["text"] == "Some content"
        assert result["url"] == "http://example.com"
        assert result["metadata"]["type"] == "web_page"

    @patch("src.services.scraper_service.trafilatura.fetch_url")
    def test_scrape_url_fetch_failed(self, mock_fetch):
        """Test scraping when fetch fails."""
        mock_fetch.return_value = None
        
        service = ScraperService()
        result = service.scrape_url("http://example.com")
        
        assert result is None

    @patch("src.services.scraper_service.trafilatura.fetch_url")
    @patch("src.services.scraper_service.trafilatura.extract")
    async def test_crawl_domain_single_page(self, mock_extract, mock_fetch):
        """Test crawling a single page."""
        mock_fetch.return_value = "<html><body>Content</body></html>"
        mock_extract.return_value = "Content"
    
        service = ScraperService()
        results = await service.crawl_domain("http://example.com", max_pages=1)
        
        assert len(results) == 1
        assert results[0]["text"] == "Content"
        assert results[0]["url"] == "http://example.com"

    @patch("src.services.scraper_service.trafilatura.fetch_url")
    @patch("src.services.scraper_service.trafilatura.extract")
    async def test_crawl_domain_recursive(self, mock_extract, mock_fetch):
        """Test recursive crawling."""
        
        # Mock fetch to return different content based on URL
        def side_effect(url):
            if url == "http://example.com":
                return '<html><body><a href="http://example.com/page1">Link</a></body></html>'
            elif url == "http://example.com/page1":
                return '<html><body>Page 1 Content</body></html>'
            return None
            
        mock_fetch.side_effect = side_effect
        mock_extract.return_value = "Extracted Text"
        
        service = ScraperService()
        results = await service.crawl_domain("http://example.com", max_pages=2)
        
        assert len(results) >= 1
        urls = [r["url"] for r in results]
        assert "http://example.com" in urls
        assert "http://example.com/page1" in urls

    def test_extract_links(self):
        """Test link extraction logic."""
        service = ScraperService()
        html = '''
        <html>
            <body>
                <a href="/page1">Internal Link</a>
                <a href="http://example.com/page2">Absolute Internal Link</a>
                <a href="http://google.com">External Link</a>
                <a href="/image.jpg">Image Link</a>
            </body>
        </html>
        '''
        
        links = service._extract_links(html, "http://example.com", "example.com")
        
        assert "http://example.com/page1" in links
        assert "http://example.com/page2" in links
        assert "http://google.com" not in links
        assert "http://example.com/image.jpg" not in links
