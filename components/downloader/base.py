from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass
import re


@dataclass
class Chapter:
    """Represents a single chapter."""
    url: str
    title: str
    number: Optional[int] = None
    
    def __post_init__(self):
        """Extract chapter number from title or URL if not provided."""
        if self.number is None:
            # Try to extract from title
            match = re.search(r'(\d+)\.?\s*', self.title)
            if match:
                self.number = int(match.group(1))
            else:
                # Try to extract from URL
                match = re.search(r'/chapters/(\d+)/', self.url)
                if match:
                    self.number = int(match.group(1))


class SiteExtractor(ABC):
    """Abstract base class for site-specific extractors."""
    
    name: str = "base"
    description: str = "Base extractor"
    requires_browser: bool = False
    
    @abstractmethod
    def extract_chapters(self, toc_url: str) -> List[Chapter]:
        """
        Extract chapter list from the Table of Contents URL.
        
        Args:
            toc_url: The URL of the Table of Contents page
            
        Returns:
            List of Chapter objects
        """
        pass
    
    @abstractmethod
    def extract_content(self, chapter_url: str, chapter: Chapter) -> Tuple[str, str]:
        """
        Extract content from a chapter URL.
        
        Args:
            chapter_url: The URL of the chapter
            chapter: The Chapter object
            
        Returns:
            Tuple of (title, content_html)
        """
        pass
    
    def get_output_filename(self, chapter: Chapter) -> str:
        """Get the output filename for a chapter."""
        if chapter.number:
            return f"ch{chapter.number:03}.xhtml"
        return f"chapter_{chapter.title[:20].replace(' ', '_')}.xhtml"


class ContentProcessor(ABC):
    """Abstract base class for content processing."""
    
    @abstractmethod
    def process(self, content: str, base_url: str) -> str:
        """Process and clean the content HTML."""
        pass


class BaseContentProcessor(ContentProcessor):
    """Default content processor."""
    
    def process(self, content: str, base_url: str) -> str:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'iframe', 'noscript']):
            tag.decompose()
        
        # Fix image URLs
        for img in soup.find_all('img', src=True):
            if not img['src'].startswith('http'):
                img['src'] = urljoin(base_url, img['src'])
        
        # Fix link URLs
        for a in soup.find_all('a', href=True):
            if not a['href'].startswith('http'):
                a['href'] = urljoin(base_url, a['href'])
        
        return str(soup)