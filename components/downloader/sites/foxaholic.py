from typing import List, Tuple
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from ..base import SiteExtractor, Chapter


class FoxaholicExtractor(SiteExtractor):
    """Extractor for Foxaholic."""
    
    name = "foxaholic"
    description = "Foxaholic (JavaScript content)"
    
    def extract_chapters(self, toc_url: str) -> List[Chapter]:
        """Extract chapters from Foxaholic TOC."""
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(toc_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        chapters = []
        
        # Find chapter list
        ul_candidates = []
        for ul in soup.find_all('ul'):
            ul_classes = ul.get('class', [])
            if {"main", "version-chap", "no-volumn", "active", "loaded"}.intersection(ul_classes):
                ul_candidates.append(ul)
        
        if not ul_candidates:
            container = soup.find('div', class_='listing-chapters_wrap')
            if container:
                ul = container.find('ul')
                if ul:
                    ul_candidates.append(ul)
        
        if not ul_candidates:
            return []
        
        for li in ul_candidates[0].find_all('li'):
            a = li.find('a', href=True)
            if a:
                url = urljoin(toc_url, a['href'])
                title = a.get_text(strip=True)
                chapters.append(Chapter(url=url, title=title))
        
        return chapters
    
    def extract_content(self, chapter_url: str, chapter: Chapter) -> Tuple[str, str]:
        """Extract content from a Foxaholic chapter."""
        if not PLAYWRIGHT_AVAILABLE:
            raise Exception("Playwright not installed")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0")
            page = context.new_page()
            
            try:
                page.goto(chapter_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_selector('div.reading-content', timeout=20000)
                
                content_div = page.query_selector('div.reading-content')
                content = content_div.inner_html() if content_div else ""
                
                title_div = page.query_selector('h4.post-title')
                title = title_div.inner_text().strip() if title_div else chapter.title
                
                return title, content
                
            finally:
                browser.close()