from typing import List, Tuple
from pathlib import Path
import json
import re
import requests
from urllib.parse import urljoin

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from ..base import SiteExtractor, Chapter


class YoruExtractor(SiteExtractor):
    """Extractor for Yoru/Lumo Stories."""
    
    name = "yoru"
    description = "Yoru/Lumo Stories (React/Next.js)"
    
    def extract_chapters(self, toc_url: str) -> List[Chapter]:
        """Extract chapters using multiple strategies."""
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠ Playwright not installed")
            return []
        
        chapters = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # Strategy 1: __NEXT_DATA__
                chapters = self._extract_from_next_data(page, toc_url)
                if chapters:
                    return chapters
                
                # Strategy 2: API Interception
                chapters = self._extract_from_api(page, context, toc_url)
                if chapters:
                    return chapters
                
                # Strategy 3: DOM Fallback
                chapters = self._extract_from_dom_fallback(page, toc_url)
                if chapters:
                    return chapters
                
            except Exception as e:
                print(f"❌ Error extracting chapters: {e}")
            finally:
                browser.close()
        
        return chapters
    
    def extract_content(self, chapter_url: str, chapter: Chapter) -> Tuple[str, str]:
        """Extract content from a chapter URL."""
        if not PLAYWRIGHT_AVAILABLE:
            raise Exception("Playwright not installed")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            try:
                page.goto(chapter_url, wait_until="domcontentloaded", timeout=60000)
                
                # Try multiple content selectors
                content_html = None
                content_selectors = [
                    "div.prose",
                    "div.prose.max-w-none",
                    "div.container-page div.prose",
                    "main.container-page",
                    "article",
                    "div[class*='prose']"
                ]
                
                for selector in content_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=3000)
                        content_div = page.query_selector(selector)
                        if content_div:
                            content_html = content_div.inner_html()
                            if content_html and len(content_html) > 50:
                                break
                    except:
                        continue
                
                # Fallback to body
                if not content_html:
                    body = page.query_selector("body")
                    if body:
                        content_html = body.inner_html()
                
                # Get title
                title_selectors = [
                    "h1.text-xl.font-semibold",
                    "h1.text-2xl.font-bold",
                    "h1",
                    "div.text-2xl.font-bold"
                ]
                
                title = chapter.title
                for selector in title_selectors:
                    try:
                        title_elem = page.query_selector(selector)
                        if title_elem:
                            title = title_elem.inner_text().strip()
                            break
                    except:
                        continue
                
                return title, content_html or ""
                
            finally:
                browser.close()
    
    def _extract_from_next_data(self, page, toc_url: str) -> List[Chapter]:
        """Extract from Next.js hydration data."""
        print("  📋 Trying __NEXT_DATA__...")
        
        try:
            page.wait_for_load_state("domcontentloaded")
            
            script_elements = page.query_selector_all('script[id="__NEXT_DATA__"]')
            if not script_elements:
                return []
            
            data = json.loads(script_elements[0].inner_text())
            book_id = self._extract_book_id(toc_url)
            
            # Common paths to find chapters
            paths = [
                ["props", "pageProps", "initialBook", "chapters"],
                ["props", "pageProps", "book", "chapters"],
                ["props", "pageProps", "chapters"],
                ["props", "initialBook", "chapters"],
                ["pageProps", "initialBook", "chapters"],
                ["pageProps", "book", "chapters"],
            ]
            
            chapters_data = None
            for path in paths:
                current = data
                try:
                    for key in path:
                        current = current.get(key, {})
                    if current and isinstance(current, list):
                        chapters_data = current
                        break
                except:
                    continue
            
            if chapters_data and book_id:
                chapters = []
                for ch in chapters_data:
                    chapter_id = ch.get('id') or ch.get('chapter_id') or ch.get('number')
                    title = ch.get('title') or ch.get('chapter_title') or f"Chapter {chapter_id}"
                    
                    if chapter_id:
                        url = f"https://lumostories.com/tw/story/{book_id}/chapters/{chapter_id}/"
                        chapters.append(Chapter(url=url, title=title, number=int(chapter_id) if str(chapter_id).isdigit() else None))
                
                return chapters
            
            return []
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []
    
    def _extract_from_api(self, page, context, toc_url: str) -> List[Chapter]:
        """Intercept API requests."""
        print("  📡 Trying API interception...")
        
        chapter_data = []
        api_caught = False
        
        def handle_response(response):
            nonlocal api_caught, chapter_data
            if 'chapter' in response.url.lower():
                try:
                    if response.status == 200:
                        data = response.json()
                        chapters = data.get('chapters') or data.get('data')
                        if chapters and isinstance(chapters, list):
                            api_caught = True
                            chapter_data = chapters
                except:
                    pass
        
        context.on("response", handle_response)
        page.goto(toc_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        context.remove_listener("response", handle_response)
        
        if api_caught and chapter_data:
            book_id = self._extract_book_id(toc_url)
            if book_id:
                chapters = []
                for ch in chapter_data:
                    chapter_id = ch.get('id')
                    title = ch.get('title') or ch.get('name') or f"Chapter {chapter_id}"
                    if chapter_id:
                        url = f"https://lumostories.com/tw/story/{book_id}/chapters/{chapter_id}/"
                        chapters.append(Chapter(url=url, title=title, number=int(chapter_id) if str(chapter_id).isdigit() else None))
                return chapters
        
        return []
    
    def _extract_from_dom_fallback(self, page, toc_url: str) -> List[Chapter]:
        """Fallback DOM extraction."""
        print("  🌐 Trying DOM fallback...")
        
        chapters = []
        
        try:
            page.wait_for_load_state("domcontentloaded")
            
            # Find chapter headings
            headings = page.query_selector_all("h1, h2, h3, h4, h5, h6")
            candidates = []
            
            for heading in headings:
                text = heading.inner_text().strip()
                if re.search(r'^\d+\.', text) or re.search(r'(SIDE STORY|EXTRA|CHAPTER)\s*\d+', text, re.IGNORECASE):
                    parent = heading.query_selector("xpath=ancestor::div[contains(@class, 'flex')]")
                    if parent:
                        candidates.append((parent, text))
            
            book_id = self._extract_book_id(toc_url)
            
            for element, text in candidates:
                # Extract chapter number
                match = re.search(r'^(\d+)\.', text)
                if match:
                    chapter_num = int(match.group(1))
                else:
                    match = re.search(r'(SIDE STORY|EXTRA|CHAPTER)\s*(\d+)', text, re.IGNORECASE)
                    if match:
                        chapter_num = int(match.group(2))
                    else:
                        continue
                
                # Extract title
                title = text.strip()
                
                # Get URL
                link = element.query_selector("a[href]")
                if link:
                    href = link.get_attribute("href")
                    if href and not href.startswith('blob:'):
                        url = urljoin(toc_url, href)
                        chapters.append(Chapter(url=url, title=title, number=chapter_num))
                elif book_id:
                    url = f"https://lumostories.com/tw/story/{book_id}/chapters/{chapter_num}/"
                    chapters.append(Chapter(url=url, title=title, number=chapter_num))
            
            return chapters
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []
    
    def _extract_book_id(self, url: str) -> str:
        """Extract book ID from URL."""
        match = re.search(r'/story/(\d+)/', url)
        return match.group(1) if match else None