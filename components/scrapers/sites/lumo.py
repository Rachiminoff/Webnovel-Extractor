import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class Chapter:
    url: str
    title: str


class LumoScraper:
    """Resilient scraper for Lumo Stories.

    Lumo chapter pages currently use URLs shaped like:
        /<lang>/story/<story-id>/read/<chapter-id>/

    The scraper deliberately treats this route pattern as a first-class signal,
    then falls back to captured JSON responses and rendered DOM inspection.
    """

    def __init__(self, output_dir: Path, sanitize_filename):
        self.output_dir = Path(output_dir)
        self.sanitize_filename = sanitize_filename
        self.debug_dir = self.output_dir / "debug"

    def _story_parts(self, toc_url):
        match = re.search(r"/(?:[a-z]{2})/story/(\d+)(?:/|$)", urlparse(toc_url).path)
        story_id = match.group(1) if match else None
        lang_match = re.search(r"^/([a-z]{2})/", urlparse(toc_url).path)
        lang = lang_match.group(1) if lang_match else None
        return story_id, lang

    def _is_chapter_url(self, url, story_id=None):
        path = urlparse(url).path.rstrip("/")
        # Known Lumo route: /en/story/211/read/1234/
        match = re.search(r"/(?:[a-z]{2})/story/(\d+)/read/(\d+)$", path)
        if match:
            return story_id is None or match.group(1) == str(story_id)
        # Generic fallback for future route variants.
        return bool(re.search(r"/(?:chapter|read)/[^/]+$", path, re.I))

    def _chapter_title_from_text(self, text, fallback):
        text = " ".join((text or "").split())
        if text and len(text) <= 250:
            return text
        return fallback

    def _dedupe(self, chapters):
        seen = set()
        result = []
        for chapter in chapters:
            if chapter.url not in seen:
                seen.add(chapter.url)
                result.append(chapter)
        return result

    def _capture_json(self, page, captured):
        def on_response(response):
            try:
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type.lower():
                    return
                # Avoid blocking page load while reading large/irrelevant responses.
                body = response.json()
                captured.append((response.url, body))
            except Exception:
                pass
        page.on("response", on_response)

    def _walk_json(self, value, base_url, story_id, results):
        if isinstance(value, dict):
            # Prefer explicit URL fields.
            for key in ("url", "href", "path", "link", "permalink"):
                candidate = value.get(key)
                if isinstance(candidate, str):
                    full = urljoin(base_url, candidate)
                    if self._is_chapter_url(full, story_id):
                        title = next((value.get(k) for k in ("title", "name", "chapter_title") if value.get(k)), None)
                        results.append(Chapter(full, self._chapter_title_from_text(title, "Untitled")))

            # Some APIs provide chapter IDs but no direct URL.
            chapter_id = value.get("chapter_id", value.get("id"))
            story_value = value.get("story_id", value.get("storyId"))
            if chapter_id is not None and story_value is not None and str(story_value) == str(story_id):
                parsed = urlparse(base_url)
                lang_match = re.search(r"^/([a-z]{2})/", parsed.path)
                lang = lang_match.group(1) if lang_match else "en"
                url = f"{parsed.scheme}://{parsed.netloc}/{lang}/story/{story_id}/read/{chapter_id}/"
                title = next((value.get(k) for k in ("title", "name", "chapter_title") if value.get(k)), None)
                results.append(Chapter(url, self._chapter_title_from_text(title, "Untitled")))

            for child in value.values():
                self._walk_json(child, base_url, story_id, results)
        elif isinstance(value, list):
            for child in value:
                self._walk_json(child, base_url, story_id, results)

    def _discover_from_dom(self, page, toc_url, story_id):
        chapters = []
        # Do NOT require visible text. Lumo's chapter cards may use nested buttons,
        # icons, or event handlers while the actual route remains in href.
        for link in page.locator("a[href]").all():
            try:
                href = link.get_attribute("href")
                if not href:
                    continue
                full = urljoin(toc_url, href)
                if self._is_chapter_url(full, story_id):
                    text = link.inner_text(timeout=1000)
                    title = self._chapter_title_from_text(text, f"Chapter {len(chapters)+1}")
                    chapters.append(Chapter(full, title))
            except Exception:
                continue
        return chapters

    def _discover_from_html(self, page, toc_url, story_id):
        """Last-resort route extraction from rendered HTML and inline scripts."""
        chapters = []
        try:
            html = page.content()
        except Exception:
            return chapters
        for href in re.findall(r"(?:https?:)?//[^\"'<>\s]+|/[^\"'<>\s]+", html):
            full = urljoin(toc_url, href.replace("\\/", "/"))
            if self._is_chapter_url(full, story_id):
                chapters.append(Chapter(full, f"Chapter {len(chapters)+1}"))
        return chapters

    def _save_debug(self, page, name, extra=None):
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        try:
            (self.debug_dir / f"{name}.html").write_text(page.content(), encoding="utf-8")
        except Exception:
            pass
        try:
            page.screenshot(path=str(self.debug_dir / f"{name}.png"), full_page=True)
        except Exception:
            pass
        if extra is not None:
            try:
                (self.debug_dir / f"{name}.json").write_text(json.dumps(extra, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            except Exception:
                pass

    def discover_chapters(self, toc_url):
        story_id, _ = self._story_parts(toc_url)
        print("🔎 Discovering Lumo Stories chapters...")
        print("   Strategy: known /story/<id>/read/<chapter-id>/ routes → network JSON → rendered DOM")

        captured = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            self._capture_json(page, captured)
            try:
                page.goto(toc_url, wait_until="domcontentloaded", timeout=60000)
                # Give the SPA time to hydrate, then scroll to trigger lazy chapter lists.
                page.wait_for_timeout(3000)
                for _ in range(6):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(800)

                chapters = self._discover_from_dom(page, toc_url, story_id)
                if not chapters:
                    for _, payload in captured:
                        self._walk_json(payload, toc_url, story_id, chapters)
                if not chapters:
                    chapters = self._discover_from_html(page, toc_url, story_id)

                chapters = self._dedupe(chapters)
                if not chapters:
                    self._save_debug(page, "lumo_toc_failed", {"captured_response_urls": [u for u, _ in captured]})
                    print(f"❌ Found 0 Lumo chapter links. Debug files saved to: {self.debug_dir}")
                else:
                    print(f"✅ Found {len(chapters)} Lumo chapter links.")
                return [(c.url, c.title) for c in chapters]
            except Exception as e:
                print(f"❌ Error discovering Lumo chapters: {e}")
                self._save_debug(page, "lumo_toc_error", {"error": str(e), "captured_response_urls": [u for u, _ in captured]})
                return []
            finally:
                context.close()
                browser.close()

    def _find_content(self, page):
        selectors = [
            "article",
            "main article",
            "[data-testid*='chapter']",
            "[class*='chapter'][class*='content']",
            "[class*='reader']",
            "[class*='prose']",
            "main",
        ]
        candidates = []
        for selector in selectors:
            try:
                for element in page.locator(selector).all():
                    text = element.inner_text(timeout=1500).strip()
                    if len(text) < 200:
                        continue
                    p_count = element.locator("p").count()
                    a_count = element.locator("a").count()
                    score = min(len(text) / 500, 20) + min(p_count * 2, 20) - min(a_count, 10)
                    if selector in ("article", "main article"):
                        score += 5
                    candidates.append((score, element))
            except Exception:
                continue
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def download_chapters(self, chapter_links):
        if not chapter_links:
            print("⚠ No Lumo chapters were discovered, so nothing was downloaded.")
            return
        print("⏳ Launching browser for Lumo Stories downloads...")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            for idx, (url, discovered_title) in enumerate(chapter_links, 1):
                print(f"📘 Downloading Lumo chapter {idx}/{len(chapter_links)}: {url}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1500)
                    content = self._find_content(page)
                    if content is None:
                        self._save_debug(page, f"lumo_chapter_{idx:03}_failed")
                        print("❌ Could not identify chapter content; debug files were saved.")
                        continue
                    # Remove reader controls and decorative SVGs before saving.
                    # The cleaner performs a second defensive pass later.
                    page.evaluate("""(root) => {
                        root.querySelectorAll('svg, use, symbol, button, input, select, textarea, hr').forEach(el => el.remove());
                        root.querySelectorAll('span, div, label, figure, a, li').forEach(el => {
                            const text = (el.innerText || '').trim().replace(/\\s+/g, ' ').toLowerCase();
                            if (['', '0', 'svg0', 'svg0 (icon)', 'icon'].includes(text)) {
                                el.remove();
                            }
                        });
                    }""", content)
                    html_content = content.inner_html()
                    title_el = page.locator("h1, h2").first
                    title = discovered_title
                    try:
                        if title_el.count():
                            candidate = title_el.inner_text().strip()
                            if candidate:
                                title = candidate
                    except Exception:
                        pass
                    filename = self.output_dir / f"ch{idx:03}.xhtml"
                    safe_title = self.sanitize_filename(title or f"Chapter_{idx:03}")
                    xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta charset="UTF-8"/><title>{safe_title}</title></head>
<body><h1>{title}</h1>{html_content}</body>
</html>'''
                    filename.write_text(xhtml, encoding="utf-8")
                    print(f"✔ Saved: {filename.name}")
                except Exception as e:
                    print(f"❌ Failed to download {url}: {e}")
                    self._save_debug(page, f"lumo_chapter_{idx:03}_error", {"error": str(e), "url": url})
            context.close()
            browser.close()
        print("✅ Lumo download run finished.")
