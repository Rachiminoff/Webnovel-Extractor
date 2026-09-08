from components.scrapers.sites.lumo import LumoScraper

class LumoService:
    def __init__(self, output_dir, sanitize_filename):
        self.scraper = LumoScraper(output_dir, sanitize_filename)

    def get_chapter_links(self, toc_url, sync_playwright):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                return self.scraper.discover(page, toc_url)
            finally:
                browser.close()

    def download_chapters(self, chapter_links, sync_playwright):
        with sync_playwright() as p:
            self.scraper.download(p, chapter_links)
