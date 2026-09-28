from __future__ import annotations

from dataclasses import dataclass

from components.downloader.base import SiteExtractor
from components.downloader.sites.static import StaticExtractor
from components.downloader.sites.yoru import YoruExtractor
from components.downloader.sites.foxaholic import FoxaholicExtractor

try:
    from components.scrapers.sites.lumo import LumoScraper
except Exception:
    LumoScraper = None

try:
    from components.downloader.sites.blogspot import BlogspotExtractor
except Exception:
    BlogspotExtractor = None


@dataclass(frozen=True)
class ExtractorInfo:
    key: str
    name: str
    description: str
    extractor: SiteExtractor
    requires_browser: bool = False


class LumoAdapter(SiteExtractor):
    name = "lumo"
    description = "Lumo Stories (route + network + DOM discovery)"
    requires_browser = True

    def __init__(self, output_dir):
        self.service = LumoScraper(output_dir, self._sanitize) if LumoScraper else None

    @staticmethod
    def _sanitize(name: str) -> str:
        return "".join(c for c in name if c.isalnum() or c in "._- ()").strip()

    def extract_chapters(self, toc_url):
        if not self.service:
            raise RuntimeError("Lumo scraper is unavailable")
        pairs = self.service.discover_chapters(toc_url)
        from components.downloader.base import Chapter
        return [Chapter(url, title, None) for url, title in pairs]

    def extract_content(self, chapter_url, chapter):
        if not self.service:
            raise RuntimeError("Lumo scraper is unavailable")
        return self.service.extract_content(chapter_url, chapter)

    def legacy_bulk_download(self, toc_url, start_number=1, pairs=None):
        """Use Lumo's proven single-browser bulk downloader.

        The modern job layer must not call Lumo chapter-by-chapter because
        that changes its browser lifecycle and can break a working scraper.
        """
        if not self.service:
            raise RuntimeError("Lumo scraper is unavailable")
        if pairs is None:
            pairs = self.service.discover_chapters(toc_url)
        stats = self.service.download_chapters(pairs, start_number=start_number)
        return pairs, stats or {"downloaded": 0, "failed": 0, "errors": []}


def build_registry(output_dir) -> dict[str, ExtractorInfo]:
    extractors: list[SiteExtractor] = [
        StaticExtractor(),
        YoruExtractor(),
        FoxaholicExtractor(),
    ]
    if LumoScraper:
        extractors.append(LumoAdapter(output_dir))
    if BlogspotExtractor:
        extractors.append(BlogspotExtractor())

    result: dict[str, ExtractorInfo] = {}
    for extractor in extractors:
        key = extractor.name.lower()
        result[key] = ExtractorInfo(
            key=key,
            name=getattr(extractor, "display_name", extractor.name.title()),
            description=extractor.description,
            extractor=extractor,
            requires_browser=bool(getattr(extractor, "requires_browser", False)),
        )
    return result
