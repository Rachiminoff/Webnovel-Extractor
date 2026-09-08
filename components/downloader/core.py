from pathlib import Path
from typing import List, Optional, Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

from .base import Chapter, SiteExtractor, ContentProcessor, BaseContentProcessor


class DownloaderEngine:
    """Core downloader engine that orchestrates the download process."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.console = Console()
        self.output_dir = output_dir or Path.home() / "Downloads" / "fan_tl_chapters"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.extractors: Dict[str, SiteExtractor] = {}
        self.processors: Dict[str, ContentProcessor] = {}
        self.default_processor = BaseContentProcessor()
    
    def register_extractor(self, extractor: SiteExtractor) -> None:
        """Register a site extractor."""
        self.extractors[extractor.name.lower()] = extractor
    
    def register_processor(self, name: str, processor: ContentProcessor) -> None:
        """Register a content processor."""
        self.processors[name.lower()] = processor
    
    def get_extractor(self, name: str) -> Optional[SiteExtractor]:
        """Get a registered extractor by name."""
        return self.extractors.get(name.lower())
    
    def list_extractors(self) -> List[tuple]:
        """List all registered extractors."""
        return [(name, ext.description) for name, ext in self.extractors.items()]
    
    def display_menu(self) -> str:
        """Display the main menu and get user choice."""
        self.console.clear()
        
        # Header
        header = Panel(
            "[bold cyan]📚 Lumo Stories Downloader[/bold cyan]\n"
            "[dim white]Modular downloader for modern React/Next.js websites[/dim white]",
            title="[bold blue]Chapter Downloader[/bold blue]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        self.console.print(header)
        self.console.print()
        
        # Menu
        menu_table = Table(show_header=False, box=box.ROUNDED, border_style="blue")
        menu_table.add_column("Option", style="bold yellow", width=10)
        menu_table.add_column("Description", style="white")
        menu_table.add_row("1", "Bulk download via Table of Contents URL")
        menu_table.add_row("2", "Single chapter download")
        menu_table.add_row("3", "List available extractors")
        menu_table.add_row("4", "Change output directory")
        menu_table.add_row("5", "Exit")
        self.console.print(menu_table)
        self.console.print()
        
        return Prompt.ask("Enter choice", choices=["1", "2", "3", "4", "5"], default="1")
    
    def display_extractors(self) -> None:
        """Display all registered extractors."""
        table = Table(title="[bold cyan]Available Extractors[/bold cyan]", box=box.ROUNDED)
        table.add_column("Name", style="bold yellow")
        table.add_column("Description", style="white")
        
        for name, desc in self.list_extractors():
            table.add_row(name, desc)
        
        self.console.print(table)
        self.console.print()
    
    def select_extractor(self) -> Optional[SiteExtractor]:
        """Let the user select an extractor."""
        self.display_extractors()
        
        choices = list(self.extractors.keys())
        if not choices:
            self.console.print("[red]❌ No extractors registered![/red]")
            return None
        
        choice = Prompt.ask(
            "Select extractor",
            choices=choices,
            default=choices[0]
        )
        return self.get_extractor(choice)
    
    def download_bulk(self, toc_url: str, extractor: SiteExtractor, start_from: int = 1) -> None:
        """Download all chapters from a TOC URL."""
        self.console.print(f"[yellow]📖 Fetching TOC from: {toc_url}[/yellow]")
        
        # Extract chapters
        chapters = extractor.extract_chapters(toc_url)
        if not chapters:
            self.console.print("[red]❌ No chapters found![/red]")
            return
        
        # Sort chapters by number (ascending - 1, 2, 3, ...)
        chapters = sorted(chapters, key=lambda c: c.number if c.number else 0)
        total = len(chapters)
        
        self.console.print(f"[green]✅ Found {total} chapters[/green]")
        
        # Ask for starting number if not provided
        if start_from == 1:
            start_from_input = Prompt.ask(
                "🔢 Start numbering from chapter number",
                default="1"
            )
            try:
                start_from = int(start_from_input)
            except ValueError:
                start_from = 1
        
        # Assign chapter numbers (ascending)
        for i, chapter in enumerate(chapters, start_from):
            if chapter.number is None:
                chapter.number = i
        
        # For display: show the range
        first_chapter = chapters[0].number if chapters[0].number else 1
        last_chapter = chapters[-1].number if chapters[-1].number else total
        
        self.console.print(f"[cyan]📚 Chapters: {first_chapter} to {last_chapter} ({total} total)[/cyan]")
        self.console.print(f"[cyan]⬆️ Downloading from Chapter 1 → Chapter {total} (ascending)[/cyan]")
        self.console.print(f"[cyan]💾 Files will be saved as ch001.xhtml → ch{total:03}.xhtml[/cyan]")
        
        # Download chapters in ascending order (1, 2, 3, ...)
        self._download_chapters(chapters, extractor)
        
        self.console.print()
        self.console.print(Panel(
            f"🎉 All {total} chapters downloaded successfully!",
            border_style="green",
            box=box.ROUNDED
        ))
        self.console.print(f"[cyan]📁 Files saved to: {self.output_dir}[/cyan]")
    
    def download_single(self, chapter_url: str, extractor: SiteExtractor) -> None:
        """Download a single chapter."""
        self.console.print(f"[yellow]📖 Downloading: {chapter_url}[/yellow]")
        
        chapter = Chapter(url=chapter_url, title="Single Chapter")
        title, content = extractor.extract_content(chapter_url, chapter)
        chapter.title = title
        
        processor = self.processors.get(extractor.name.lower(), self.default_processor)
        cleaned_content = processor.process(content, chapter_url)
        
        filename = self.output_dir / extractor.get_output_filename(chapter)
        self._save_chapter(filename, title, cleaned_content)
        
        self.console.print(f"[green]✔ Saved: {filename.name}[/green]")
    
    def _download_chapters(self, chapters: List[Chapter], extractor: SiteExtractor) -> None:
        """
        Internal method to download chapters with progress bar.
        Downloads in ascending order (1, 2, 3, ...) and saves with same numbers.
        """
        total = len(chapters)
        processor = self.processors.get(extractor.name.lower(), self.default_processor)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("[cyan]Downloading chapters...", total=total)
            
            for idx, chapter in enumerate(chapters, 1):
                # The chapter number is its position in the sorted list
                chapter_num = idx
                
                progress.update(
                    task,
                    description=f"[cyan]Downloading chapter {chapter_num}/{total}: {chapter.title[:40]}..."
                )
                
                try:
                    title, content = extractor.extract_content(chapter.url, chapter)
                    cleaned_content = processor.process(content, chapter.url)
                    
                    # Save with the correct ascending number
                    filename = self.output_dir / f"ch{chapter_num:03}.xhtml"
                    self._save_chapter(filename, title, cleaned_content)
                    
                    progress.update(task, advance=1)
                    
                except Exception as e:
                    self.console.print(f"[red]❌ Failed to download chapter {chapter_num}: {e}[/red]")
                    progress.update(task, advance=1)
                    continue
    
    def _save_chapter(self, filename: Path, title: str, content: str) -> None:
        """Save a chapter to a file."""
        xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
{content}
</body>
</html>"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(xhtml)
    
    def run(self) -> None:
        """Main entry point for the downloader."""
        while True:
            choice = self.display_menu()
            
            if choice == "5":  # Exit
                break
            
            if choice == "3":  # List extractors
                self.display_extractors()
                Prompt.ask("Press Enter to continue")
                continue
            
            if choice == "4":  # Change output directory
                new_dir = Prompt.ask("Enter new output directory path")
                try:
                    self.output_dir = Path(new_dir)
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    self.console.print(f"[green]✅ Output directory changed to: {self.output_dir}[/green]")
                except Exception as e:
                    self.console.print(f"[red]❌ Failed to change directory: {e}[/red]")
                Prompt.ask("Press Enter to continue")
                continue
            
            extractor = self.select_extractor()
            if not extractor:
                continue
            
            if choice == "1":  # Bulk download
                toc_url = Prompt.ask("Enter Table of Contents URL")
                self.download_bulk(toc_url, extractor)
                Prompt.ask("Press Enter to continue")
            
            elif choice == "2":  # Single download
                chapter_url = Prompt.ask("Enter Chapter URL")
                self.download_single(chapter_url, extractor)
                Prompt.ask("Press Enter to continue")