from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table


class UI:
    def __init__(self) -> None:
        self.console = Console()

    def clear(self) -> None:
        self.console.clear()

    def header(self, subtitle: str = "Download • Clean • Build • Convert") -> None:
        self.console.print(
            Panel.fit(
                "[bold bright_cyan]📚 WEBNOVEL TOOLKIT[/bold bright_cyan]\n"
                f"[dim]{subtitle}[/dim]",
                border_style="bright_blue",
                padding=(1, 2),
            )
        )

    def section(self, title: str, subtitle: str | None = None) -> None:
        body = f"[bold]{title}[/bold]"
        if subtitle:
            body += f"\n[dim]{subtitle}[/dim]"
        self.console.print(Panel(body, border_style="cyan", box=box.ROUNDED))

    def menu(self, title: str, options: Iterable[tuple[str, str, str]], default: str = "1") -> str:
        table = Table(title=title, box=box.ROUNDED, header_style="bold cyan")
        table.add_column("", width=4, justify="center", style="bold yellow")
        table.add_column("Action", style="bold white")
        table.add_column("Description", style="dim")
        for key, action, description in options:
            table.add_row(key, action, description)
        self.console.print(table)
        return Prompt.ask("[bold cyan]Choose[/bold cyan]", default=default)

    def path_prompt(self, label: str, default: Path | None = None) -> Path:
        value = Prompt.ask(label, default=str(default) if default else None)
        return Path(value.strip().strip('"')).expanduser()

    def url_prompt(self, label: str = "URL") -> str:
        return Prompt.ask(label).strip()

    def pause(self) -> None:
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")

    def success(self, message: str) -> None:
        self.console.print(f"[green]✓ {message}[/green]")

    def info(self, message: str) -> None:
        self.console.print(f"[cyan]• {message}[/cyan]")

    def warning(self, message: str) -> None:
        self.console.print(f"[yellow]⚠ {message}[/yellow]")

    def error(self, message: str) -> None:
        self.console.print(f"[bold red]✗ {message}[/bold red]")


    @staticmethod
    def friendly_error(exc: Exception | str) -> str:
        text = str(exc).strip()
        lower = text.lower()
        if not text:
            return "The operation failed, but no additional details were provided."
        if "timeout" in lower or "timed out" in lower:
            return "The website took too long to respond. It may be slow or temporarily unavailable."
        if "404" in lower:
            return "The requested page was not found. The website may have changed its URL or page structure."
        if "403" in lower or "forbidden" in lower:
            return "The website refused the request. It may be blocking automated access."
        if "err_name_not_resolved" in lower or "name or service not known" in lower or "connectionerror" in lower:
            return "The website could not be reached. Check your internet connection and the URL."
        if "could not identify" in lower or "no chapter content" in lower:
            return "The page loaded, but the extractor could not find the chapter text. The website may have changed its layout."
        if "playwright" in lower and "install" in lower:
            return "The browser component is not installed correctly. Run Diagnostics and install the required browser."
        return "The chapter could not be processed because the website returned an unexpected response."

    def confirm(self, message: str, default: bool = True) -> bool:
        return Confirm.ask(message, default=default)

    def summary(self, title: str, rows: list[tuple[str, str]], border_style: str = "green") -> None:
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        table.add_column(style="dim")
        table.add_column(style="bold")
        for key, value in rows:
            table.add_row(key, value)
        self.console.print(Panel(table, title=title, border_style=border_style))

    @contextmanager
    def status(self, message: str):
        with self.console.status(message, spinner="dots"):
            yield
