import pytest
from unittest.mock import MagicMock, patch
from src.services.academic_scraper import AcademicSourceScraper

class TestAcademicSourceScraper:
    
    @pytest.fixture
    def scraper(self):
        return AcademicSourceScraper()

    @patch("src.services.academic_scraper.requests.get")
    def test_fetch_semantic_scholar_success(self, mock_get, scraper):
        """Test successful Semantic Scholar fetching."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "Test Paper",
                    "abstract": "This is a test abstract.",
                    "url": "http://test.com",
                    "year": 2023,
                    "venue": "Test Journal",
                    "isOpenAccess": True,
                    "openAccessPdf": {"url": "http://test.com/pdf"}
                }
            ]
        }
        mock_get.return_value = mock_response

        results = scraper._fetch_semantic_scholar("test query", limit=1)
        
        assert len(results) == 1
        assert results[0]["title"] == "Test Paper"
        assert results[0]["url"] == "http://test.com/pdf" # Prefer PDF
        assert results[0]["source_api"] == "Semantic Scholar"

    @patch("src.services.academic_scraper.requests.get")
    def test_fetch_semantic_scholar_retry(self, mock_get, scraper):
        """Test Semantic Scholar retry logic on 429."""
        # First call 429, second call 200
        mock_429 = MagicMock()
        mock_429.status_code = 429
        
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"data": []}
        
        mock_get.side_effect = [mock_429, mock_200]

        with patch("time.sleep") as mock_sleep:
            results = scraper._fetch_semantic_scholar("test query", limit=1)
            
            assert mock_get.call_count == 2
            mock_sleep.assert_called_once()
            assert isinstance(results, list)

    @patch("src.services.academic_scraper.Crossref")
    def test_fetch_crossref_success(self, mock_crossref_cls, scraper):
        """Test successful Crossref fetching."""
        mock_instance = MagicMock()
        mock_instance.works.return_value = {
            "message": {
                "items": [
                    {
                        "title": ["Crossref Paper"],
                        "abstract": "<jats:p>Abstract content</jats:p>",
                        "URL": "http://crossref.com",
                        "DOI": "10.1000/1",
                        "publisher": "Publisher X",
                        "created": {"date-parts": [[2023]]}
                    }
                ]
            }
        }
        scraper.crossref = mock_instance # Replace usage

        results = scraper._fetch_crossref("test query", limit=1)
        
        assert len(results) == 1
        assert results[0]["title"] == "Crossref Paper"
        assert results[0]["abstract"].strip() == "Abstract content" # Cleaned tags
        assert results[0]["source_api"] == "Crossref"

    @patch("src.services.academic_scraper.AcademicSourceScraper._fetch_semantic_scholar")
    @patch("src.services.academic_scraper.AcademicSourceScraper._fetch_crossref")
    def test_search_sources_integration(self, mock_crossref, mock_sem, scraper):
        """Test the main search_sources method aggregates results."""
        mock_sem.return_value = [{"title": "Sem Result"}]
        mock_crossref.return_value = [{"title": "Cross Result"}]

        results = scraper.search_sources("query", limit=5, category="Botanik")
        
        assert len(results) == 2
        
        # Verify specific logic for Botanik category (filtering ISSN)
        mock_crossref.assert_called_with("query", 5, filter_issn='1664-462X')

        # Verify default logic
        scraper.search_sources("query", limit=5, category="General")
        mock_crossref.assert_called_with("query", 5) # No filter_issn
