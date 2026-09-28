from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass

from rich import box
from rich.table import Table

from cli.ui import UI
from core.config import AppConfig, ConfigStore
from core.jobs import DownloadJob, SingleDownloadJob
from core.logging_utils import configure_logging
from core.registry import build_registry
from components.downloader.base import Chapter


@dataclass
class SessionDownloadState:
    extractor_key: str | None = None
    toc_url: str | None = None
    chapters: list[Chapter] | None = None

    def matches(self, extractor_key: str, toc_url: str) -> bool:
        return self.extractor_key == extractor_key and self.toc_url == toc_url and bool(self.chapters)


def module_available(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


class ToolkitApp:
    def __init__(self) -> None:
        self.ui = UI()
        self.config_store = ConfigStore()
        self.config = self.config_store.load()
        self.paths = self.config.paths
        self.paths.ensure()
        self.logger = configure_logging(self.paths.logs)
        self.registry = build_registry(self.paths.chapters)
        # Temporary session memory only. It is intentionally not written to disk.
        self.session_download = SessionDownloadState()

    def dependency_report(self) -> None:
        self.ui.clear()
        self.ui.header("Environment • Dependencies • Diagnostics")
        table = Table(title="Environment", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("Component")
        table.add_column("Status")
        required = [("Python", True), ("requests", module_available("requests")),
                    ("BeautifulSoup", module_available("bs4")), ("Playwright", module_available("playwright")),
                    ("EbookLib", module_available("ebooklib")), ("Rich", module_available("rich"))]
        for name, ok in required:
            table.add_row(name, "[green]✓ Ready[/green]" if ok else "[red]✗ Missing[/red]")
        for name, command in (("Pandoc", "pandoc"), ("Calibre", "ebook-convert")):
            table.add_row(name, "[green]✓ Found[/green]" if shutil.which(command) else "[yellow]— Not installed[/yellow]")
        table.add_row("WeasyPrint", "[green]✓ Ready[/green]" if module_available("weasyprint") else "[yellow]— Optional[/yellow]")
        self.ui.console.print(table)
        self.ui.summary("Storage", [
            ("Workspace", str(self.paths.root)),
            ("Chapters", str(self.paths.chapters)),
            ("Cleaned", str(self.paths.cleaned)),
            ("EPUB", str(self.paths.ebooks)),
            ("PDF", str(self.paths.pdf)),
            ("Logs", str(self.paths.logs)),
        ], border_style="cyan")
        self.ui.pause()

    def select_extractor(self):
        options = []
        keys = list(self.registry)
        for i, key in enumerate(keys, 1):
            info = self.registry[key]
            browser = "browser required" if info.requires_browser else "HTTP/static"
            options.append((str(i), info.name, f"{info.description} • {browser}"))
        options.append(("0", "Back", "Return to the previous menu"))
        choice = self.ui.menu("Sources", options, default="1")
        if choice == "0":
            return None
        try:
            return self.registry[keys[int(choice) - 1]].extractor
        except (ValueError, IndexError):
            self.ui.error("Invalid source selection")
            return None

    def download(self) -> None:
        self.ui.clear(); self.ui.header("Download chapters")
        extractor = self.select_extractor()
        if extractor is None:
            return
        mode = self.ui.menu("Download mode", [
            ("1", "Bulk download", "Discover every chapter from a table-of-contents URL"),
            ("2", "Single chapter", "Download one chapter URL"),
            ("0", "Back", "Return to the main menu"),
        ])
        if mode == "0": return
        if mode == "1":
            url = self.ui.url_prompt("Table of Contents URL")
            start = self.ui.console.input("Start chapter number [1]: ").strip() or "1"
            try: start_number = max(1, int(start))
            except ValueError: start_number = 1

            extractor_key = getattr(extractor, "name", extractor.__class__.__name__).lower()
            cached_chapters = None
            if self.session_download.matches(extractor_key, url):
                cached_chapters = self.session_download.chapters
                self.ui.success(
                    f"Using the TOC already discovered earlier in this session ({len(cached_chapters)} chapters)."
                )
            else:
                self.ui.console.print("[dim]This TOC has not been discovered in this session yet.[/dim]")

            job = DownloadJob(
                extractor, url, self.paths.chapters, start_number,
                self.config.retries, self.config.pause_between_retries,
                self.logger, self.ui, discovered_chapters=cached_chapters
            )
            try:
                chapters, result = job.run()
                self.session_download = SessionDownloadState(
                    extractor_key=extractor_key, toc_url=url, chapters=chapters
                )
                self.ui.summary("Download complete", [
                    ("Discovered", str(len(chapters))), ("Downloaded", str(result.succeeded)),
                    ("Skipped", str(result.skipped)), ("Failed", str(result.failed)), ("Output", str(self.paths.chapters))
                ], border_style="green" if result.failed == 0 else "yellow")
                for title, error in result.errors[:10]:
                    self.ui.error(f"{title}: {self.ui.friendly_error(error)}")
                    self.ui.console.print(f"    [dim]Technical details: {error}[/dim]")
            except Exception as exc:
                self.logger.exception("Bulk download failed")
                self.ui.error(self.ui.friendly_error(exc))
        elif mode == "2":
            url = self.ui.url_prompt("Chapter URL")
            try:
                path = SingleDownloadJob(extractor, url, self.paths.chapters, self.config.retries, self.config.pause_between_retries, self.logger).run()
                self.ui.success(f"Saved {path}")
            except Exception as exc:
                self.logger.exception("Single download failed")
                self.ui.error(self.ui.friendly_error(exc))
        self.ui.pause()

    def clean(self) -> None:
        from components.Cleaner import ChapterCleaner
        self.ui.clear(); self.ui.header("Clean chapters")
        source = self.paths.chapters
        files = list(source.glob("*.html")) + list(source.glob("*.xhtml"))
        if not files:
            self.ui.warning(f"No HTML/XHTML chapters found in {source}"); self.ui.pause(); return
        self.ui.summary("Cleaning job", [("Input", str(source)), ("Files", str(len(files))), ("Output", str(self.paths.cleaned))], border_style="cyan")
        if not self.ui.confirm("Start cleaning?", True): return
        cleaner = ChapterCleaner(source, self.paths.cleaned)
        try:
            cleaner.clean_all_html(mode=2)
            self.ui.success(f"Cleaned chapters written to {self.paths.cleaned}")
        except Exception as exc:
            self.logger.exception("Cleaning failed")
            self.ui.error(self.ui.friendly_error(exc))
        self.ui.pause()

    def compile_epub(self) -> None:
        from components.compiler import EpubCompiler
        self.ui.clear(); self.ui.header("Build EPUB")
        compiler = EpubCompiler(workspace=self.paths.cleaned, output_dir=self.paths.ebooks)
        files = compiler.get_xhtml_files()
        if not files:
            self.ui.warning(f"No XHTML files found in {self.paths.cleaned}"); self.ui.pause(); return
        choice = self.ui.menu("Compilation engine", [
            ("1", "Pandoc", "Fast, external EPUB builder"),
            ("2", "Calibre", "Use ebook-convert"),
            ("3", "EbookLib", "Pure Python EPUB generation"),
            ("0", "Back", "Return to the main menu"),
        ])
        if choice == "0": return
        if choice == "1" and not compiler.check_pandoc(): self.ui.error("Pandoc is not installed."); self.ui.pause(); return
        if choice == "2" and not compiler.check_ebook_convert(): self.ui.error("Calibre is not installed."); self.ui.pause(); return
        if choice == "3" and compiler.epub is None: self.ui.error("EbookLib is not installed."); self.ui.pause(); return
        metadata = compiler.get_metadata_interactive(self.ui)
        try:
            output = compiler.compile(choice, files, metadata)
            self.ui.success(f"EPUB saved to {output}")
        except Exception as exc:
            self.logger.exception("EPUB compilation failed")
            self.ui.error(self.ui.friendly_error(exc))
        self.ui.pause()

    def convert_pdf(self) -> None:
        self.ui.clear(); self.ui.header("Convert EPUB → PDF")
        if not module_available("weasyprint"):
            self.ui.warning("WeasyPrint is unavailable. Install it and its platform dependencies first.")
            self.ui.pause(); return
        from components.converter import EPUBToPDF
        converter = EPUBToPDF(output_dir=self.paths.pdf)
        mode = self.ui.menu("Conversion mode", [
            ("1", "Single EPUB", "Convert one EPUB file"),
            ("2", "Folder", "Convert every EPUB in a folder"),
            ("0", "Back", "Return to the main menu"),
        ])
        if mode == "0": return
        fullpage = self.ui.confirm("Make cover/illustration pages full-page?", False)
        try:
            if mode == "1":
                epub_path = self.ui.path_prompt("EPUB path")
                output = converter.epub_to_pdf_with_cover(str(epub_path), str(self.paths.pdf / f"{epub_path.stem}.pdf"), fullpage)
                self.ui.success(f"PDF saved to {output}")
            else:
                folder = self.ui.path_prompt("Folder containing EPUB files", self.paths.ebooks)
                results = converter.convert_all_in_folder(folder, fullpage)
                self.ui.summary("Conversion complete", [("Succeeded", str(results[0])), ("Failed", str(results[1])), ("Output", str(self.paths.pdf))], border_style="green" if results[1] == 0 else "yellow")
        except Exception as exc:
            self.logger.exception("PDF conversion failed")
            self.ui.error(str(exc))
        self.ui.pause()

    def settings(self) -> None:
        self.ui.clear(); self.ui.header("Settings")
        choice = self.ui.menu("Configuration", [
            ("1", "Output directory", "Change the root workspace used by all workflows"),
            ("2", "Retry count", f"Current: {self.config.retries}"),
            ("3", "Reset defaults", "Restore conservative defaults"),
            ("0", "Back", "Return to the main menu"),
        ])
        if choice == "1":
            root = self.ui.path_prompt("Workspace directory", self.config.output_root)
            self.config.output_root = root; self.config.paths.ensure(); self.config_store.save(self.config)
            self.paths = self.config.paths; self.logger = configure_logging(self.paths.logs); self.registry = build_registry(self.paths.chapters)
            self.ui.success(f"Workspace changed to {root}")
        elif choice == "2":
            raw = self.ui.console.input(f"Retries [{self.config.retries}]: ").strip()
            if raw:
                try: self.config.retries = max(0, min(10, int(raw))); self.config_store.save(self.config)
                except ValueError: self.ui.error("Retries must be a number")
        elif choice == "3":
            if self.ui.confirm("Reset all toolkit settings?", False):
                self.config = AppConfig(); self.config.paths.ensure(); self.config_store.save(self.config)
                self.paths = self.config.paths; self.logger = configure_logging(self.paths.logs); self.registry = build_registry(self.paths.chapters)
                self.ui.success("Defaults restored")
        self.ui.pause()

    def run(self) -> None:
        while True:
            self.ui.clear(); self.ui.header()
            self.ui.summary("Workspace", [("Output", str(self.paths.root)), ("Sources", str(len(self.registry))), ("Retries", str(self.config.retries))], border_style="cyan")
            choice = self.ui.menu("Main Menu", [
                ("1", "📥 Download", "Discover and download chapters"),
                ("2", "🧹 Clean", "Remove site noise and produce normalized XHTML"),
                ("3", "📚 Build EPUB", "Compile cleaned chapters into an ebook"),
                ("4", "📄 Convert PDF", "Convert EPUB files to PDF"),
                ("5", "🔧 Settings", "Workspace and retry configuration"),
                ("6", "🩺 Diagnostics", "Inspect dependencies, tools, and storage"),
                ("7", "📋 Sources", "View registered site extractors"),
                ("0", "🚪 Exit", "Close the toolkit"),
            ])
            if choice == "1": self.download()
            elif choice == "2": self.clean()
            elif choice == "3": self.compile_epub()
            elif choice == "4": self.convert_pdf()
            elif choice == "5": self.settings()
            elif choice == "6": self.dependency_report()
            elif choice == "7":
                self.ui.clear(); self.ui.header("Registered sources")
                for info in self.registry.values():
                    self.ui.console.print(f"[bold cyan]{info.name}[/bold cyan] — {info.description}")
                self.ui.pause()
            elif choice == "0":
                self.ui.console.print("[dim]Goodbye.[/dim]"); break


if __name__ == "__main__":
    ToolkitApp().run()
