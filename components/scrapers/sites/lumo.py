import json
import re
import time
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
        if not text or len(text) > 250:
            return fallback

        # Lumo can expose its age-verification prompt as a heading. It is UI
        # text, not the chapter title, so never allow it into chapter metadata.
        normalized = text.casefold().strip(" .!?…")
        blocked = {
            "are you 18 or older",
            "are you 18+",
            "18 or older",
            "18+",
        }
        if normalized in blocked or "are you 18 or older" in normalized:
            return fallback
        return text

    def _extract_chapter_title(self, page, fallback, content=None):
        """Return a real chapter title without letting Lumo UI overwrite it."""
        # The TOC title is the most reliable source because it is obtained from
        # the chapter listing rather than from the reader UI. Keep it whenever
        # it is valid instead of allowing an age-gate heading to replace it.
        reliable_fallback = self._chapter_title_from_text(fallback, "")
        if reliable_fallback:
            return reliable_fallback

        candidates = []

        # Prefer headings inside the actual chapter body.
        if content is not None:
            try:
                for selector in ("h1", "h2", "h3"):
                    for element in content.locator(selector).all():
                        candidates.append(element.inner_text(timeout=1000).strip())
            except Exception:
                pass

        # Then inspect page metadata, which is less likely to be affected by
        # the age-verification dialog than the first visible h1/h2.
        for selector in (
            "meta[property='og:title']",
            "meta[name='twitter:title']",
        ):
            try:
                value = page.locator(selector).first.get_attribute("content")
                if value:
                    candidates.append(value.strip())
            except Exception:
                pass

        # Finally inspect headings, but explicitly ignore modal/dialog UI.
        try:
            for selector in ("h1", "h2", "h3"):
                for element in page.locator(selector).all():
                    try:
                        if element.locator("xpath=ancestor-or-self::*[@role='dialog']").count():
                            continue
                        candidates.append(element.inner_text(timeout=1000).strip())
                    except Exception:
                        continue
        except Exception:
            pass

        # Only use a page-derived candidate if it is not an age gate or other
        # obvious Lumo chrome. Otherwise retain the title discovered from TOC.
        for candidate in candidates:
            title = self._chapter_title_from_text(candidate, "")
            if title:
                return title
        return self._chapter_title_from_text(fallback, fallback)

    def _is_placeholder_title(self, title):
        normalized = " ".join((title or "").split()).casefold().strip(" .!?…")
        if normalized in {
            "", "untitled", "read", "read chapter", "open", "continue",
            "start reading", "18+", "18 or older", "are you 18 or older",
        }:
            return True
        # A synthetic fallback such as "Chapter 12" should not prevent a
        # real title from the API/DOM from replacing it. Titles containing a
        # suffix (e.g. "Chapter 12: The Meeting") are real titles.
        return bool(re.fullmatch(r"(?:chapter|ch\.?)\s*\d+", normalized, re.I))

    def _merge_chapters(self, primary, secondary):
        """Merge chapter sources while preferring real titles over UI labels."""
        merged = {}
        order = []
        for chapter in list(primary) + list(secondary):
            if chapter.url not in merged:
                merged[chapter.url] = chapter
                order.append(chapter.url)
            elif self._is_placeholder_title(merged[chapter.url].title) and not self._is_placeholder_title(chapter.title):
                merged[chapter.url] = chapter
        return [merged[url] for url in order]

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
                        title = next((value.get(k) for k in ("title", "chapter_title", "chapterTitle", "chapter_name", "chapterName", "display_title", "displayTitle", "name") if value.get(k)), None)
                        results.append(Chapter(full, self._chapter_title_from_text(title, "Untitled")))

            # Some APIs provide chapter IDs but no direct URL.
            chapter_id = value.get("chapter_id", value.get("id"))
            story_value = value.get("story_id", value.get("storyId"))
            if chapter_id is not None and story_value is not None and str(story_value) == str(story_id):
                parsed = urlparse(base_url)
                lang_match = re.search(r"^/([a-z]{2})/", parsed.path)
                lang = lang_match.group(1) if lang_match else "en"
                url = f"{parsed.scheme}://{parsed.netloc}/{lang}/story/{story_id}/read/{chapter_id}/"
                title = next((value.get(k) for k in ("title", "chapter_title", "chapterTitle", "chapter_name", "chapterName", "display_title", "displayTitle", "name") if value.get(k)), None)
                results.append(Chapter(url, self._chapter_title_from_text(title, "Untitled")))

            for child in value.values():
                self._walk_json(child, base_url, story_id, results)
        elif isinstance(value, list):
            for child in value:
                self._walk_json(child, base_url, story_id, results)

    def _discover_from_dom(self, page, toc_url, story_id):
        """Discover chapter links in one browser-side pass.

        Avoid thousands of individual Playwright locator calls on large TOCs.
        Lumo can expose hundreds of chapter cards, so querying each ancestor from
        Python can make discovery appear frozen. The browser collects the small
        amount of metadata we need in one evaluate call; title selection remains
        deterministic in Python below.
        """
        chapters = []
        try:
            rows = page.evaluate(r"""() => {
                const out = [];
                const action = new Set([
                    'read', 'read chapter', 'open', 'continue', 'start reading',
                    'show more', 'free', 'locked', 'unlock', 'subscribe'
                ]);
                const clean = value => String(value || '').replace(/\s+/g, ' ').trim();
                const add = (anchor) => {
                    const href = anchor.getAttribute('href');
                    if (!href) return;
                    const values = [];
                    for (const attr of [
                        'aria-label', 'title', 'data-title', 'data-chapter-title',
                        'data-name', 'data-chapter-name'
                    ]) {
                        const v = clean(anchor.getAttribute(attr));
                        if (v) values.push(v);
                    }
                    let node = anchor;
                    for (let level = 0; level < 4 && node; level++, node = node.parentElement) {
                        for (const el of node.querySelectorAll('h1,h2,h3,h4,[class*="title"],[class*="chapter-name"],[class*="chapter-title"]')) {
                            const v = clean(el.innerText);
                            if (v && v.length <= 250) values.push(v);
                        }
                        const raw = clean(node.innerText);
                        if (raw) {
                            for (const line of raw.split(/\n+/)) {
                                const v = clean(line);
                                if (v && v.length <= 250 && !action.has(v.toLowerCase())) values.push(v);
                            }
                        }
                    }
                    out.push({ href, values });
                };
                for (const anchor of document.querySelectorAll('a[href]')) add(anchor);
                return out;
            }""")
        except Exception:
            return chapters

        action_labels = {
            "read", "read chapter", "open", "continue", "start reading",
            "show more", "free", "locked", "unlock", "subscribe",
        }

        def clean_candidate(value):
            value = " ".join((value or "").split())
            if not value or len(value) > 250:
                return ""
            normalized = value.casefold().strip(" .!?…")
            if normalized in action_labels or self._is_placeholder_title(value):
                return ""
            if "are you 18 or older" in normalized:
                return ""
            # Lumo chapter cards may combine the real title and UI metadata in
            # one text node, for example:
            # "Actual Chapter Title Last updated: 1 year ago • 2,148 words Read".
            # Strip only the metadata portion so the real title is preserved.
            value = re.sub(r"\s*last\s+updated\s*:.*$", "", value, flags=re.I).strip(" -•|·")
            value = re.sub(r"\s*[•|·]\s*[\d,]+\s+words?\b.*$", "", value, flags=re.I).strip(" -•|·")
            value = re.sub(r"\s+(?:read|read\s+chapter)\s*$", "", value, flags=re.I).strip(" -•|·")
            if not value:
                return ""
            return value

        def choose_candidate(candidates):
            cleaned = []
            seen = set()
            for value in candidates:
                value = clean_candidate(value)
                if value and value.casefold() not in seen:
                    seen.add(value.casefold())
                    cleaned.append(value)
            if not cleaned:
                return ""

            def score(value):
                low = value.casefold()
                score = 0
                if re.search(r"\bchapter\s*\d+\b|\bch\.?\s*\d+\b", low):
                    score += 30
                if ":" in value or " - " in value or " — " in value:
                    score += 10
                if 3 <= len(value.split()) <= 18:
                    score += 8
                if re.fullmatch(r"[\d,\s]+", value):
                    score -= 30
                if re.search(r"\b(?:days?|hours?|minutes?|years?)\s+ago\b", low):
                    score -= 30
                if re.fullmatch(r"(?:free|locked|unlock|subscribe)", low):
                    score -= 30
                score -= max(0, len(value) - 120) / 20
                return score
            return max(cleaned, key=score)

        for row in rows or []:
            try:
                href = row.get("href")
                full = urljoin(toc_url, href or "")
                if not self._is_chapter_url(full, story_id):
                    continue
                title = choose_candidate(row.get("values", []))
                if not title:
                    title = f"Chapter {len(chapters) + 1}"
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
                print("   Loading the story page...")
                try:
                    page.goto(toc_url, wait_until="domcontentloaded", timeout=20000)
                except Exception as exc:
                    # A slow/blocked request must not leave discovery apparently
                    # frozen. The partially loaded DOM may still contain the TOC.
                    print(f"   ⚠ Story page load did not finish ({type(exc).__name__}); checking the page anyway...")

                # Give the SPA a short hydration window, then perform only a
                # couple of scrolls to trigger lazy-loaded chapter cards.
                page.wait_for_timeout(1200)
                for _ in range(2):
                    try:
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    except Exception:
                        pass
                    page.wait_for_timeout(350)

                print("   Checking rendered chapter links...")
                chapters = self._discover_from_dom(page, toc_url, story_id)
                json_chapters = []
                for _, payload in captured:
                    self._walk_json(payload, toc_url, story_id, json_chapters)

                # Keep DOM order, but let captured API data replace generic
                # labels such as "Read" when it contains the real title.
                chapters = self._merge_chapters(chapters, json_chapters)
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

    def _find_content(self, page, timeout_ms=15000):
        """Find the chapter body, allowing the JS-rendered reader time to hydrate.

        Lumo is a client-rendered application, so a fixed sleep is unreliable: some
        chapters appear quickly while others take several seconds. We poll the same
        candidate selectors until useful text is actually present.
        """
        selectors = [
            "article",
            "main article",
            "[data-testid*='chapter']",
            "[data-testid*='content']",
            "[class*='chapter'][class*='content']",
            "[class*='chapter-content']",
            "[class*='reader']",
            "[class*='prose']",
            "main",
        ]
        deadline = time.monotonic() + timeout_ms / 1000
        best = None
        best_score = -1

        while time.monotonic() < deadline:
            candidates = []
            for selector in selectors:
                try:
                    for element in page.locator(selector).all():
                        text = element.inner_text(timeout=1000).strip()
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

            if candidates:
                candidates.sort(key=lambda item: item[0], reverse=True)
                best_score, best = candidates[0]
                # A substantial text block is enough to proceed.
                if best_score >= 5:
                    return best

            page.wait_for_timeout(400)

        return best

    def extract_content(self, chapter_url, chapter):
        """Extract a single chapter for the workflow/job layer."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(chapter_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(500)
                content = self._find_content(page, timeout_ms=15000)
                if content is None:
                    self._save_debug(page, "lumo_single_failed", {"url": chapter_url})
                    raise RuntimeError("Could not identify Lumo chapter content")
                content.evaluate("""(root) => {
                    root.querySelectorAll('svg, use, symbol, button, input, select, textarea, hr').forEach(el => el.remove());
                }""")
                html_content = content.inner_html()
                title = self._extract_chapter_title(page, chapter.title, content)
                return title, html_content
            finally:
                context.close()
                browser.close()

    def download_chapters(self, chapter_links, start_number=1):
        if not chapter_links:
            print("⚠ No Lumo chapters were discovered, so nothing was downloaded.")
            return {"downloaded": 0, "skipped": 0, "failed": 0, "errors": []}
        stats = {"downloaded": 0, "skipped": 0, "failed": 0, "errors": []}
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Check the filesystem before launching Chromium. This makes interrupted
        # downloads cheap to resume: completed chapters are skipped immediately.
        pending = []
        # The first discovered TOC entry gets the number the user supplied.
        # Each following entry counts downward: 236, 235, 234, ...
        for offset, item in enumerate(chapter_links):
            idx = start_number - offset
            if idx <= 0:
                print(f"⚠ Starting chapter number {start_number} is too small for {len(chapter_links)} discovered chapters.")
                break
            filename = self.output_dir / f"ch{idx:03}.xhtml"
            if filename.exists() and filename.stat().st_size > 0:
                stats["skipped"] += 1
                print(f"⏭ Skipping Lumo chapter {idx}/{len(chapter_links)}: {filename.name} already exists")
            else:
                pending.append((idx, item))

        if not pending:
            print("✅ All discovered chapters are already downloaded. Nothing else to do.")
            return stats

        print("⏳ Launching browser for Lumo Stories downloads...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            for idx, (url, discovered_title) in pending:
                print(f"📘 Downloading Lumo chapter {idx}/{len(chapter_links)}: {url}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(500)
                    content = self._find_content(page, timeout_ms=15000)
                    if content is None:
                        self._save_debug(page, f"lumo_chapter_{idx:03}_failed")
                        print("❌ Could not identify chapter content; debug files were saved.")
                        continue
                    # Remove reader controls and decorative SVGs before saving.
                    # The cleaner performs a second defensive pass later.
                    content.evaluate(r"""(root) => {
                        root.querySelectorAll('svg, use, symbol, button, input, select, textarea, hr').forEach(el => el.remove());
                        root.querySelectorAll('span, div, label, figure, a, li').forEach(el => {
                            const text = (el.innerText || '').trim().replace(/\s+/g, ' ').toLowerCase();
                            if (['', '0', 'svg0', 'svg0 (icon)', 'icon'].includes(text)) {
                                el.remove();
                            }
                        });
                    }""")
                    html_content = content.inner_html()
                    title = self._extract_chapter_title(page, discovered_title, content)
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
                    stats["downloaded"] += 1
                except Exception as e:
                    print(f"❌ Failed to download {url}: {e}")
                    stats["failed"] += 1
                    stats["errors"].append({"chapter": idx, "url": url, "error": str(e)})
                    self._save_debug(page, f"lumo_chapter_{idx:03}_error", {"error": str(e), "url": url})
            context.close()
            browser.close()
        print("✅ Lumo download run finished.")
        return stats
