from typing import List, Tuple
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from ..base import SiteExtractor, Chapter


class StaticExtractor(SiteExtractor):
    """Fallback extractor for static HTML sites."""
    
    name = "static"
    description = "Static HTML (generic fallback)"
    
    def extract_chapters(self, toc_url: str) -> List[Chapter]:
        """Extract chapters from static HTML."""
        response = requests.get(toc_url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        chapters = []
        
        # Look for chapter containers
        containers = [
            soup.find("div", class_="max-h-[500px]"),
            soup.find("div", class_="chapters-list"),
            soup.find("div", class_="chapter-list"),
        ]
        
        for container in containers:
            if container:
                # Look for links
                for a in container.find_all('a', href=True):
                    text = a.get_text(strip=True)
                    if text and any(k in text.lower() for k in ['chapter', 'part', 'extra']):
                        url = urljoin(toc_url, a['href'])
                        chapters.append(Chapter(url=url, title=text))
                break
        
        # If no specific container found, look for any chapter-like links
        if not chapters:
            chapter_keywords = ['chapter', 'part', 'extra', 'volume', 'act']
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True).lower()
                if any(k in text for k in chapter_keywords):
                    url = urljoin(toc_url, a['href'])
                    chapters.append(Chapter(url=url, title=a.get_text(strip=True)))
        
        return chapters
    
    def extract_content(self, chapter_url: str, chapter: Chapter) -> Tuple[str, str]:
        """Extract content from static HTML."""
        response = requests.get(chapter_url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find content container
        content_selectors = [
            'div.content',
            'div.post-body',
            'div.entry-content',
            'article',
            'main',
            'body'
        ]
        
        content = ""
        for selector in content_selectors:
            container = soup.select_one(selector)
            if container:
                content = str(container)
                break
        
        title = soup.find('h1')
        title_text = title.get_text(strip=True) if title else chapter.title
        
        return title_text, content