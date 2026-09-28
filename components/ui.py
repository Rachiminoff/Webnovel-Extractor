from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.rule import Rule
from rich import box

console = Console(highlight=False)

APP_TITLE = "WEBNOVEL TOOLKIT"
TAGLINE = "Download • Clean • Compile • Convert"

def clear():
    console.clear()

def header(title=APP_TITLE, subtitle=TAGLINE):
    console.print(
        Panel.fit(
            f"[bold bright_cyan]📚 {title}[/bold bright_cyan]\n"
            f"[dim]{subtitle}[/dim]",
            border_style="bright_blue",
            padding=(1, 3),
        )
    )

def section(title, icon=""):
    console.print()
    console.print(Rule(f"[bold cyan]{icon} {title}[/bold cyan]".strip(), style="cyan"))
    console.print()

def success(message):
    console.print(f"[green]✓[/green] {message}")

def warning(message):
    console.print(f"[yellow]⚠[/yellow] {message}")

def error(message):
    console.print(f"[bold red]✗[/bold red] {message}")

def info(message):
    console.print(f"[cyan]•[/cyan] {message}")

def prompt(message, default=None):
    return Prompt.ask(f"[bold cyan]{message}[/bold cyan]", default=default)

def choose(title, options, default=None):
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column("Key", style="bold bright_cyan", width=5, justify="center")
    table.add_column("Action", style="white")
    for key, label in options:
        table.add_row(str(key), label)
    console.print(Panel(table, title=f"[bold]{title}[/bold]", border_style="cyan", padding=(0, 1)))
    valid = [str(k) for k, _ in options]
    return Prompt.ask("[bold cyan]Select[/bold cyan]", choices=valid, default=str(default) if default is not None else None)

def pause():
    Prompt.ask("\n[dim]Press Enter to return to the main menu[/dim]", default="")

def operation_panel(icon, title, description=None, style="cyan"):
    body = f"[bold]{title}[/bold]"
    if description:
        body += f"\n[dim]{description}[/dim]"
    console.print(Panel(body, title=icon, border_style=style, padding=(1, 2)))

def result_panel(title, lines, style="green"):
    body = "\n".join(lines)
    console.print(Panel(body, title=title, border_style=style, padding=(1, 2)))
