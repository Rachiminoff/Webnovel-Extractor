from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeRemainingColumn

from components.downloader.base import Chapter, SiteExtractor


@dataclass
class JobResult:
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.succeeded + self.failed + self.skipped


class DownloadJob:
    def __init__(
        self,
        extractor: SiteExtractor,
        toc_url: str,
        output_dir: Path,
        start_number: int = 1,
        retries: int = 2,
        retry_delay: float = 1.0,
        logger: logging.Logger | None = None,
        ui=None,
        discovered_chapters: list[Chapter] | None = None,
    ) -> None:
        self.extractor = extractor
        self.toc_url = toc_url
        self.output_dir = Path(output_dir)
        self.start_number = start_number
        self.retries = retries
        self.retry_delay = retry_delay
        self.logger = logger or logging.getLogger("webnovel_toolkit")
        self.ui = ui
        self.discovered_chapters = discovered_chapters

    def _write_chapter(self, chapter: Chapter, number: int) -> Path:
        title, content = self.extractor.extract_content(chapter.url, chapter)
        if not content.strip():
            raise RuntimeError("The extractor returned empty chapter content")
        filename = self.extractor.get_output_filename(
            Chapter(url=chapter.url, title=title or chapter.title, number=number)
        )
        path = self.output_dir / filename
        safe_title = (title or chapter.title).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">\n<head><meta charset="UTF-8"/><title>{safe_title}</title></head>\n<body><h1>{safe_title}</h1>{content}</body>\n</html>'''
        path.write_text(xhtml, encoding="utf-8")
        return path

    def _retry(self, fn: Callable[[], Path], label: str) -> Path:
        attempts = self.retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as exc:
                last_error = exc
                self.logger.exception("Download failed: %s (attempt %s/%s)", label, attempt, attempts)
                if attempt < attempts:
                    if self.ui:
                        self.ui.warning(f"{label} failed; retrying ({attempt}/{self.retries})")
                    time.sleep(self.retry_delay)
        raise last_error or RuntimeError("Unknown download error")

    def run(self) -> tuple[list[Chapter], JobResult]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        result = JobResult()
        self.logger.info("Starting download job: %s", self.toc_url)

        # Some mature site scrapers have a proven bulk workflow that manages
        # browser lifetime internally. Do not force those scrapers through the
        # generic per-chapter pipeline; doing so can change their behavior.
        legacy_bulk = getattr(self.extractor, "legacy_bulk_download", None)
        if callable(legacy_bulk):
            pairs = [(chapter.url, chapter.title) for chapter in self.discovered_chapters] if self.discovered_chapters is not None else None
            pairs, stats = legacy_bulk(self.toc_url, self.start_number, pairs=pairs)
            chapters = [Chapter(url=url, title=title, number=None) for url, title in pairs]
            result.succeeded = int(stats.get("downloaded", 0))
            result.skipped = int(stats.get("skipped", 0))
            result.failed = int(stats.get("failed", 0))
            result.errors = [
                (f"Chapter {item.get('chapter', '?')}", item.get("error", "Unknown error"))
                for item in stats.get("errors", [])
            ]
            return chapters, result

        chapters = self.discovered_chapters if self.discovered_chapters is not None else self.extractor.extract_chapters(self.toc_url)
        chapters = sorted(chapters, key=lambda c: (c.number is None, c.number or 0, c.title.lower()))
        if not chapters:
            raise RuntimeError("No chapters were discovered")

        for index, chapter in enumerate(chapters, self.start_number):
            if chapter.number is None:
                chapter.number = index

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(),
            MofNCompleteColumn(), TaskProgressColumn(), TimeRemainingColumn(), transient=False,
            console=self.ui.console if self.ui else None,
        ) as progress:
            task = progress.add_task("Downloading chapters", total=len(chapters))
            for index, chapter in enumerate(chapters, self.start_number):
                label = f"Chapter {index:03}"
                try:
                    existing = self.output_dir / self.extractor.get_output_filename(Chapter(chapter.url, chapter.title, index))
                    if existing.exists() and existing.stat().st_size > 0:
                        result.skipped += 1
                        progress.update(task, advance=1, description=f"Skipping {label}")
                        continue
                    path = self._retry(lambda ch=chapter, i=index: self._write_chapter(ch, i), label)
                    result.succeeded += 1
                    progress.update(task, advance=1, description=f"Saved {path.name}")
                except Exception as exc:
                    result.failed += 1
                    result.errors.append((chapter.title or label, str(exc)))
                    progress.update(task, advance=1, description=f"Failed {label}")
        return chapters, result


class SingleDownloadJob:
    def __init__(self, extractor: SiteExtractor, url: str, output_dir: Path, retries: int = 2, retry_delay: float = 1.0, logger=None):
        self.extractor = extractor
        self.url = url
        self.output_dir = Path(output_dir)
        self.retries = retries
        self.retry_delay = retry_delay
        self.logger = logger or logging.getLogger("webnovel_toolkit")

    def run(self) -> Path:
        chapter = Chapter(url=self.url, title="Chapter")
        job = DownloadJob(self.extractor, self.url, self.output_dir, retries=self.retries, retry_delay=self.retry_delay, logger=self.logger)
        return job._retry(lambda: job._write_chapter(chapter, chapter.number or 1), "Single chapter")
