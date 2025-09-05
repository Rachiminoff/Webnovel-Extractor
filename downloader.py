import os
import sys
import requests
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class ChapterDownloader:
    def __init__(self):
        # Set up output directory under user's Downloads folder
        self.downloads_path = Path.home() / "Downloads"
        self.output_dir = self.downloads_path / "fan_tl_chapters"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    def sanitize_filename(self, name):
        # Clean the filename to allow only safe characters for filesystems
        return "".join(c for c in name if c.isalnum() or c in "._- ()").strip()

    # --- STATIC DOWNLOAD ---
    def get_chapter_links_static(self, toc_url):
        print("📖 Fetching TOC (static)...")
        res = self.session.get(toc_url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        chapter_links = []

        chapters_section = soup.find("section", class_="chapters-section")
        if chapters_section:
            chapter_items = chapters_section.select("div.novel-chapters > div.chapter-item")
            for item in chapter_items:
                a = item.find("a", href=True)
                if a:
                    full_url = urljoin(toc_url, a['href'])
                    chapter_links.append(full_url)

        if not chapter_links:
            chapter_keywords = [
                "chapter", "part", "mail", "extra", "final", "ending", "prologue", "epilogue",
                "volume", "vol", "act", "story", "installment", "segment", "section", "scene", "chapter-item"
            ]
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True).lower()
                if any(k in text for k in chapter_keywords):
                    full_url = urljoin(toc_url, a['href'])
                    chapter_links.append(full_url)

            if not chapter_links:
                list_keywords = [
                    "wp-block-list", "chapter-list", "chapters", "toc", "post-list", "chapter-section",
                    "entry-list", "index", "list"
                ]
                ul = None
                for ul_tag in soup.find_all('ul'):
                    ul_class = ul_tag.get('class', [])
                    if any(any(keyword in c.lower() for keyword in list_keywords) for c in ul_class):
                        ul = ul_tag
                        break
                if ul:
                    for li in ul.find_all('li'):
                        for a in li.find_all('a', href=True):
                            full_url = urljoin(toc_url, a['href'])
                            chapter_links.append(full_url)

        seen = set()
        unique_links = []
        for link in chapter_links:
            if link not in seen:
                unique_links.append(link)
                seen.add(link)

        print(f"🔗 Final chapter count: {len(unique_links)}")
        return [(url, f"Chapter {i+1}") for i, url in enumerate(unique_links)]

    def download_html_static_file(self, url, filename):
        print(f"Downloading (static): {url}")
        try:
            r = self.session.get(url)
            r.raise_for_status()
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(r.text)
            print(f"✔ Saved: {filename.name}")
        except Exception as e:
            print(f"❌ Failed to download {url}: {e}")

    def download_html_static_bulk(self, chapter_links):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        while True:
            start_input = input("🔢 Start numbering from chapter number (e.g. 1 or 10): ").strip()
            if start_input.isdigit():
                start_chapter = int(start_input)
                break
            else:
                print("Invalid input. Please enter a number.")

        print(f"📥 Starting static downloads from Chapter {start_chapter}...")

        for offset, (url, _) in enumerate(chapter_links):
            chapter_num = start_chapter + offset
            filename = self.output_dir / f"ch{chapter_num:03}.xhtml"
            self.download_html_static_file(url, filename)

        print("✅ All static chapters downloaded.")

    # --- YORUAPP DOWNLOAD ---
    def get_chapter_links_yoru(self, toc_url):
        print("Rendering TOC and extracting YoruApp chapter links…")
        links = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(toc_url, wait_until="networkidle")
                page.wait_for_selector('a:has-text("Read")', timeout=20000)
                buttons = page.query_selector_all('a:has-text("Read")')

                for btn in buttons:
                    href = btn.get_attribute("href")
                    title_node = btn.query_selector("span")
                    title = title_node.inner_text().strip() if title_node else "Untitled"
                    if href and href.startswith("read/"):
                        full_url = urljoin(toc_url, href)
                        links.append((full_url, title))
            except Exception as e:
                print(f"❌ Error extracting Yoru chapter links: {e}")
            finally:
                browser.close()

        print(f"✅ Found {len(links)} Yoru chapters.")
        return links

    def download_chapters_yoru(self, chapter_links):
        print("⏳ Launching browser for Yoru downloads...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            for idx, (url, _) in enumerate(reversed(chapter_links), 1):
                print(f"📘 Downloading Yoru chapter {idx}: {url}")
                try:
                    page.goto(url, wait_until="networkidle")
                    page.wait_for_selector('div.prose.max-w-none', timeout=20000)
                    content_div = page.query_selector('div.prose.max-w-none')
                    html_content = content_div.inner_html()
                    title_div = page.query_selector('div.mt-4.text-2xl.font-bold')
                    title = title_div.inner_text().strip() if title_div else f"Chapter_{idx:03}"
                    safe_title = self.sanitize_filename(title)
                    filename = self.output_dir / f"ch{idx:03}.xhtml"
                    xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{safe_title}</title></head>
<body>
<h1>{title}</h1>
{html_content}
</body>
</html>"""
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(xhtml)
                    print(f"✔ Saved: {filename.name}")
                except Exception as e:
                    print(f"❌ Failed to download {url}: {e}")
            browser.close()
        print("✅ All Yoru chapters downloaded.")

    # --- FOXAHOLIC DOWNLOAD ---
    def get_chapter_links_foxaholic(self, toc_url):
        print("Fetching Foxaholic TOC (static)...")
        headers = {"User-Agent": "Mozilla/5.0"}
        res = self.session.get(toc_url, headers=headers)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        chapter_links = []

        possible_uls = soup.find_all('ul')
        ul_candidates = []
        for ul in possible_uls:
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
            print("❌ Could not find chapter list.")
            return []

        for li in ul_candidates[0].find_all('li'):
            a = li.find('a', href=True)
            if a:
                full_url = urljoin(toc_url, a['href'])
                chapter_links.append((full_url, a.get_text(strip=True)))

        print(f"🔗 Found {len(chapter_links)} Foxaholic chapter links.")
        return chapter_links

    def download_chapters_foxaholic(self, chapter_links):
        print("⏳ Launching browser for Foxaholic downloads...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0")
            page = context.new_page()
            for idx, (url, _) in enumerate(reversed(chapter_links), 1):
                print(f"📘 Downloading Foxaholic chapter {idx}: {url}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_selector('div.reading-content', timeout=20000)
                    content_div = page.query_selector('div.reading-content')
                    html_content = content_div.inner_html()
                    title_div = page.query_selector('h4.post-title')
                    title = title_div.inner_text().strip() if title_div else f"Chapter_{idx:03}"
                    safe_title = self.sanitize_filename(title)
                    filename = self.output_dir / f"ch{idx:03}.xhtml"
                    xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{safe_title}</title></head>
<body>
<h1>{title}</h1>
{html_content}
</body>
</html>"""
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(xhtml)
                    print(f"✔ Saved: {filename.name}")
                except Exception as e:
                    print(f"❌ Failed to download {url}: {e}")
            context.close()
            browser.close()
        print("✅ All Foxaholic chapters downloaded.")

    # --- BLOGSPOT ---
    def get_chapter_links_blogspot_playwright(self, toc_url):
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠ Playwright not installed.")
            return []
        print("⏳ Rendering TOC with Playwright for Blogspot...")
        chapter_links = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(toc_url, wait_until="networkidle")
            chapter_items = page.query_selector_all('section.chapters-section div.novel-chapters div.chapter-item')
            for item in chapter_items:
                a = item.query_selector('a[href]')
                if a:
                    href = a.get_attribute('href')
                    full_url = urljoin(toc_url, href)
                    chapter_links.append(full_url)
            browser.close()
        return [(url, f"Chapter {i+1}") for i, url in enumerate(chapter_links)]

    def download_chapters_blogspot_playwright(self, chapter_links):
        if not PLAYWRIGHT_AVAILABLE:
            print("⚠ Playwright not installed.")
            return
        print("⏳ Launching browser for Blogspot downloads (XHTML wrap)...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0")
            page = context.new_page()
            total = len(chapter_links)
            for idx, (url, title_hint) in enumerate(chapter_links, 1):
                print(f"📘 Downloading Blogspot chapter {idx} of {total}: {url}")
                try:
                    page.goto(url, wait_until="networkidle", timeout=60000)
                    selectors = [
                        'article.post', 'div.post-body', 'div.post',
                        'article[itemprop="articleBody"]', 'div.blog-posts', 'div.entry-content'
                    ]
                    content_html = ""
                    for sel in selectors:
                        try:
                            page.wait_for_selector(sel, timeout=3000)
                        except Exception:
                            continue
                        elem = page.query_selector(sel)
                        if elem:
                            content_html = elem.inner_html().strip()
                            if content_html:
                                break
                    if not content_html:
                        content_html = page.content()
                    soup = BeautifulSoup(content_html, 'html.parser')
                    for tag in soup(['script', 'style', 'iframe', 'noscript']):
                        tag.decompose()
                    for img in soup.find_all('img', src=True):
                        img['src'] = urljoin(url, img['src'])
                    cleaned_html = str(soup)
                    safe_title = self.sanitize_filename(
                        title_hint if title_hint.strip() else f"Chapter_{idx:03}"
                    )
                    filename = self.output_dir / f"ch{idx:03}.xhtml"
                    xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <title>{safe_title}</title>
</head>
<body>
  <h1>{safe_title}</h1>
  {cleaned_html}
</body>
</html>"""
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(xhtml)
                    print(f"✔ Saved: {filename.name}")
                except Exception as e:
                    print(f"❌ Failed to download {url}: {e}")
            context.close()
            browser.close()
        print("✅ All Blogspot chapters downloaded as XHTML.")

    # --- SINGLE CHAPTER ---
    def download_single_chapter(self, mode, site_type=None):
        chapter_url = input("Enter chapter URL: ").strip()
        if not chapter_url:
            print("No URL entered.")
            return
        filename = self.output_dir / "chapter_single.xhtml"
        if mode == "1":
            self.download_html_static_file(chapter_url, filename)
        else:
            if not PLAYWRIGHT_AVAILABLE:
                print("⚠ Playwright not installed.")
                return
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                try:
                    page.goto(chapter_url, wait_until="networkidle")
                    if site_type == 'yoru':
                        selector = 'div.prose.max-w-none'
                    elif site_type == 'foxaholic':
                        selector = 'div.text-left'
                    else:
                        selector = 'body'
                    page.wait_for_selector(selector, timeout=20000)
                    content_div = page.query_selector(selector)
                    html_content = content_div.inner_html() if content_div else ""
                    title = chapter_url.split('/')[-1] or "chapter"
                    safe_title = self.sanitize_filename(title)
                    filename = self.output_dir / f"{safe_title}.xhtml"
                    xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{safe_title}</title></head>
<body>
<h1>{safe_title}</h1>
{html_content}
</body>
</html>"""
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(xhtml)
                    print(f"✔ Saved: {filename.name}")
                except Exception as e:
                    print(f"❌ Failed to download {chapter_url}: {e}")
                browser.close()

    # --- RUN ---
    def run(self):
        print("Choose download source:")
        print("1. Bulk download via Table of Contents URL")
        print("2. Single chapter download")
        source_mode = input("Enter choice (1 or 2): ").strip()

        print("Choose download type:")
        print("1. Static (plain HTML site)")
        print("2. YoruApp (JS content, needs browser)")
        print("3. Foxaholic (JS content, needs browser)")
        print("4. Blogspot (JS content, needs browser)")
        render_mode = input("Enter type (1, 2, 3 or 4): ").strip()

        if source_mode == "1":
            toc_url = input("Enter Table of Contents URL: ").strip()
            if render_mode == "1":
                chapter_links = self.get_chapter_links_static(toc_url)
                self.download_html_static_bulk(chapter_links)
            elif render_mode == "2":
                chapter_links = self.get_chapter_links_yoru(toc_url)
                self.download_chapters_yoru(chapter_links)
            elif render_mode == "3":
                chapter_links = self.get_chapter_links_foxaholic(toc_url)
                self.download_chapters_foxaholic(chapter_links)
            elif render_mode == "4":
                chapter_links = self.get_chapter_links_blogspot_playwright(toc_url)
                self.download_chapters_blogspot_playwright(chapter_links)
        else:
            site_type = None
            if render_mode == "2":
                site_type = "yoru"
            elif render_mode == "3":
                site_type = "foxaholic"
            self.download_single_chapter(render_mode, site_type=site_type)


if __name__ == "__main__":
    ChapterDownloader().run()
