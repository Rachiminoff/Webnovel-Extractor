from typing import List, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from ..base import SiteExtractor, Chapter


class BlogspotExtractor(SiteExtractor):
    name = "blogspot"
    description = "Blogspot (rendered chapter pages)"
    requires_browser = True

    def extract_chapters(self, toc_url: str) -> List[Chapter]:
        if sync_playwright is None:
            raise RuntimeError("Playwright is required for Blogspot")
        links = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(toc_url, wait_until="networkidle", timeout=60000)
                for item in page.query_selector_all("section.chapters-section div.novel-chapters div.chapter-item"):
                    link = item.query_selector("a[href]")
                    if link:
                        href = link.get_attribute("href")
                        if href:
                            links.append(Chapter(urljoin(toc_url, href), link.inner_text().strip() or f"Chapter {len(links)+1}"))
            finally:
                browser.close()
        return links

    def extract_content(self, chapter_url: str, chapter: Chapter) -> Tuple[str, str]:
        if sync_playwright is None:
            raise RuntimeError("Playwright is required for Blogspot")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0")
            page = context.new_page()
            try:
                page.goto(chapter_url, wait_until="networkidle", timeout=60000)
                content_html = ""
                for selector in ('article.post', 'div.post-body', 'div.post', 'article[itemprop="articleBody"]', 'div.blog-posts', 'div.entry-content'):
                    try:
                        page.wait_for_selector(selector, timeout=3000)
                    except Exception:
                        continue
                    elem = page.query_selector(selector)
                    if elem:
                        content_html = elem.inner_html().strip()
                        if content_html:
                            break
                if not content_html:
                    content_html = page.content()
                soup = BeautifulSoup(content_html, "html.parser")
                for tag in soup(["script", "style", "iframe", "noscript"]):
                    tag.decompose()
                for img in soup.find_all("img", src=True):
                    img["src"] = urljoin(chapter_url, img["src"])
                title = chapter.title
                heading = page.query_selector("h1, h2, .post-title")
                if heading:
                    title = heading.inner_text().strip() or title
                return title, str(soup)
            finally:
                context.close()
                browser.close()
