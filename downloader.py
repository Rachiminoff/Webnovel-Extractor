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

    def get_chapter_links_static(self, toc_url):
        """
        Scrapes chapter URLs from a static HTML Table of Contents page.
        Looks for anchor tags with keywords related to chapters.
        """
        print("📖 Fetching TOC (static)...")
        res = self.session.get(toc_url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        chapter_keywords = [
            "chapter", "part", "mail", "extra", "final", "ending", "prologue", "epilogue"
        ]

        candidate_links = []
        # Find all anchor tags and filter those whose text matches chapter keywords
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True).lower()
            if any(keyword in text for keyword in chapter_keywords):
                full_url = urljoin(toc_url, href)
                candidate_links.append(full_url)

        # Remove duplicates while keeping order
        chapter_links = list(dict.fromkeys(candidate_links))
        print(f"🔗 Found {len(chapter_links)} candidate chapters.")
        # Return list of tuples (url, "Chapter X")
        return [(url, f"Chapter {i+1}") for i, url in enumerate(chapter_links)]
    
    def get_chapter_links_rendered(self, toc_url):
        """
        Scrapes chapter URLs from a JavaScript-rendered site like YoruApp using Playwright.
        It waits for the page to load and looks for "Read" buttons linking to chapters.
        """
        print("Rendering TOC and extracting chapter links…")
        links = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(toc_url, wait_until="networkidle")
                # Wait until "Read" links appear on page
                page.wait_for_selector('a:has-text("Read")', timeout=20000)
                buttons = page.query_selector_all('a:has-text("Read")')

                for btn in buttons:
                    href = btn.get_attribute("href")
                    title_node = btn.query_selector("span")
                    title = title_node.inner_text().strip() if title_node else "Untitled"
                    # Only consider links starting with "read/"
                    if href and href.startswith("read/"):
                        full_url = urljoin(toc_url, href)
                        links.append((full_url, title))

            except Exception as e:
                print(f"❌ Error extracting chapter links: {e}")
            finally:
                browser.close()

        if links:
            print(f"✅ Found {len(links)} chapters.")
        else:
            print("❌ No chapters found.")
        return links

    def download_html_static_file(self, url, filename):
        """
        Download a single static HTML chapter and save to a file.
        """
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
        """
        Download all static chapters in bulk using the TOC links.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print("📥 Starting static downloads...")
        for idx, (url, _) in enumerate(chapter_links, 1):
            filename = self.output_dir / f"ch{idx:03}.xhtml"
            self.download_html_static_file(url, filename)
        print("✅ All static chapters downloaded.")

    def download_chapters_rendered(self, chapter_links):
        """
        Download chapters from JavaScript-rendered pages using Playwright,
        extracting only the main content div.
        """
        print("⏳ Launching browser...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Downloads chapters in reverse order for some reason (e.g. newest last)
            for idx, (url, _) in enumerate(reversed(chapter_links), 1):
                print(f"📘 Downloading chapter {idx}: {url}")
                try:
                    page.goto(url, wait_until="networkidle")
                    # Wait for main content selector
                    page.wait_for_selector('div.prose.max-w-none', timeout=20000)

                    content_div = page.query_selector('div.prose.max-w-none')
                    html_content = content_div.inner_html()

                    title_div = page.query_selector('div.mt-4.text-2xl.font-bold')
                    title = title_div.inner_text().strip() if title_div else f"Chapter_{idx:03}"

                    safe_title = self.sanitize_filename(title)
                    filename = self.output_dir / f"ch{idx:03}.xhtml"

                    # Wrap extracted HTML in XHTML template for EPUB compatibility
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
        print("✅ All chapters downloaded in reverse order.")

    def download_single_chapter(self, mode):
        """
        Download a single chapter by URL. Mode 1 for static HTML,
        mode 2 for rendered JS content.
        """
        chapter_url = input("Enter chapter URL: ").strip()
        if not chapter_url:
            print("No URL entered. Exiting.")
            return

        filename = self.output_dir / "chapter_single.txt"
        if mode == "1":
            # Static download
            self.download_html_static_file(chapter_url, filename)
        else:
            # Rendered download using Playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                try:
                    page.goto(chapter_url, wait_until="networkidle")
                    page.wait_for_selector('div.prose.max-w-none', timeout=20000)
                    content_div = page.query_selector('div.prose.max-w-none')
                    text = content_div.inner_text()
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(text)
                    print(f"✔ Saved: {filename.name}")
                except Exception as e:
                    print(f"❌ Failed to render {chapter_url}: {e}")
                browser.close()

    def run(self):
        """
        Main interactive run method asking user for download mode and source,
        then triggering the appropriate download methods.
        """
        print("Choose download source:")
        print("1. Bulk download via Table of Contents URL")
        print("2. Single chapter download")
        source_mode = input("Enter choice (1 or 2): ").strip()

        if source_mode not in {"1", "2"}:
            print("Invalid input. Exiting.")
            sys.exit(1)

        print("Choose download type:")
        print("1. Static (plain HTML site)")
        print("2. YoruApp (JS content, needs browser)")
        render_mode = input("Enter type (1 or 2): ").strip()

        if render_mode not in {"1", "2"}:
            print("Invalid input. Exiting.")
            sys.exit(1)

        if render_mode == "2" and not PLAYWRIGHT_AVAILABLE:
            print("⚠ You chose rendered mode but Playwright is not installed.")
            print("Run: pip install playwright && playwright install")
            sys.exit(1)

        if source_mode == "1":
            toc_url = input("Enter Table of Contents URL: ").strip()
            if not toc_url:
                print("No TOC URL provided. Exiting.")
                sys.exit(1)

            if render_mode == "1":
                # Static TOC scraping + bulk download
                chapter_links = self.get_chapter_links_static(toc_url)
                self.download_html_static_bulk(chapter_links)
            else:
                # Rendered TOC scraping + rendered downloads
                chapter_links = self.get_chapter_links_rendered(toc_url)
                if not chapter_links:
                    print("No chapter links found.")
                    sys.exit(1)
                self.download_chapters_rendered(chapter_links)
        else:
            # Single chapter download
            self.download_single_chapter(render_mode)


if __name__ == "__main__":
    downloader = ChapterDownloader()
    downloader.run()
