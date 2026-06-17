import importlib
import subprocess
import sys
import shutil
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import box


console = Console()

REQUIRED_MODULES = {
    "bs4": "beautifulsoup4",
    "requests": "requests",
    "playwright": "playwright",
    "ebooklib": "ebooklib",
    "lxml": "lxml",
    "rich": "rich",
}

OPTIONAL_MODULES = {
    "weasyprint": "weasyprint",
}

PDF_AVAILABLE = False


def success(msg):
    console.print(f"[green]✓ {msg}[/green]")


def warning(msg):
    console.print(f"[yellow]⚠ {msg}[/yellow]")


def error(msg):
    console.print(f"[bold red]✗ {msg}[/bold red]")


def info(msg):
    console.print(f"[cyan]{msg}[/cyan]")


def install_packages(packages):

    if not packages:
        return True

    console.print(
        Panel(
            "[cyan]Installing missing Python packages...[/cyan]\n"
            "This may take a few minutes.",
            title="📦 Dependencies",
            border_style="cyan"
        )
    )

    try:

        with console.status(
            "[bold green]Installing packages...",
            spinner="dots"
        ):

            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    *packages
                ]
            )

        success("Packages installed successfully")

        return True

    except Exception as e:

        error("Failed installing packages")
        console.print(e)

        return False


def check_weasyprint():

    global PDF_AVAILABLE

    try:

        importlib.import_module("weasyprint")

        PDF_AVAILABLE = True
        success("weasyprint")

    except ImportError:

        warning("weasyprint not installed")
        console.print(
            "[dim]PDF conversion will be unavailable.[/dim]"
        )

        PDF_AVAILABLE = False

    except OSError:

        warning("weasyprint installed but GTK libraries are missing")

        console.print(
            "\n[cyan]Install GTK Runtime:[/cyan]\n"
            "https://github.com/tschoonj/"
            "GTK-for-Windows-Runtime-Environment-Installer/releases\n"
        )

        console.print(
            "[dim]After installation:\n"
            "1. Restart your PC or terminal\n"
            "2. Run this program again[/dim]"
        )

        PDF_AVAILABLE = False

    except Exception as e:

        warning("WeasyPrint unavailable")
        console.print(e)

        PDF_AVAILABLE = False

def ensure_dependencies():

    console.clear()

    console.print(
        Panel.fit(
            "[bold bright_cyan]📚 WEBNOVEL TOOLKIT[/bold bright_cyan]\n"
            "[dim]Download • Clean • Compile • Convert[/dim]",
            border_style="bright_blue"
        )
    )

    info("Checking dependencies...\n")

    missing_packages = []

    table = Table(
        title="Python Dependencies",
        box=box.ROUNDED,
        header_style="bold cyan"
    )

    table.add_column("Package")
    table.add_column("Status")

    for module_name, package_name in REQUIRED_MODULES.items():

        try:

            importlib.import_module(module_name)

            table.add_row(
                package_name,
                "[green]✓ Installed[/green]"
            )

        except ImportError:

            table.add_row(
                package_name,
                "[red]✗ Missing[/red]"
            )

            missing_packages.append(package_name)

    console.print(table)

    # Install missing packages
    if missing_packages:

        success_install = install_packages(missing_packages)

        if not success_install:

            Prompt.ask(
                "\nPress Enter to exit",
                default=""
            )

            sys.exit(1)

    console.print()

    check_weasyprint()

    console.print()

    #
    # Playwright Chromium
    #

    console.print(
        Panel.fit(
            "[bold cyan]🌐 Playwright Chromium[/bold cyan]",
            border_style="cyan"
        )
    )

    try:

        with console.status(
            "[bold green]Checking Chromium browser...",
            spinner="dots"
        ):

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "playwright",
                    "install",
                    "chromium"
                ],
                check=True
            )

        success("Chromium browser ready")

    except Exception as e:

        warning("Could not verify Chromium browser")
        console.print(e)

    #
    # External tools
    #

    console.print()

    tools_table = Table(
        title="External Tools",
        box=box.ROUNDED,
        header_style="bold cyan"
    )

    tools_table.add_column("Tool")
    tools_table.add_column("Status")

    pandoc_found = shutil.which("pandoc") is not None
    calibre_found = shutil.which("ebook-convert") is not None

    if pandoc_found:

        tools_table.add_row(
            "Pandoc",
            "[green]✓ Installed[/green]"
        )

    else:

        tools_table.add_row(
            "Pandoc",
            "[yellow]⚠ Not Found[/yellow]"
        )

    if calibre_found:

        tools_table.add_row(
            "Calibre (ebook-convert)",
            "[green]✓ Installed[/green]"
        )

    else:

        tools_table.add_row(
            "Calibre (ebook-convert)",
            "[yellow]⚠ Not Found[/yellow]"
        )

    console.print(tools_table)

    if not pandoc_found:

        console.print(
            "[yellow]Pandoc is required for EPUB Compiler Mode 1[/yellow]"
        )
        console.print(
            "https://pandoc.org/installing.html\n"
        )

    if not calibre_found:

        console.print(
            "[yellow]Calibre is required for EPUB Compiler Mode 2[/yellow]"
        )
        console.print(
            "https://calibre-ebook.com/download\n"
        )

    #
    # PDF status
    #

    console.print()

    if PDF_AVAILABLE:

        console.print(
            Panel(
                "[green]PDF conversion ready[/green]",
                title="📄 PDF",
                border_style="green"
            )
        )

    else:

        console.print(
            Panel(
                "[yellow]PDF conversion unavailable[/yellow]\n"
                "EPUB creation still works normally.",
                title="📄 PDF",
                border_style="yellow"
            )
        )

    success("Dependency check complete")

    time.sleep(2)

# Run dependency checks BEFORE loading components
ensure_dependencies()

from components.downloader import ChapterDownloader
from components.Cleaner import ChapterCleaner
from components.compiler import EpubCompiler

try:
    from components.converter import EPUBToPDF
except Exception:
    EPUBToPDF = None

class MainController:

    def __init__(self):

        self.downloader = ChapterDownloader()
        self.cleaner = ChapterCleaner()
        self.compiler = EpubCompiler()

        if PDF_AVAILABLE and EPUBToPDF:
            self.converter = EPUBToPDF()
        else:
            self.converter = None


    def show_header(self):

        console.print()

        console.print(
            Panel.fit(
                "[bold bright_cyan]📚 WEBNOVEL TOOLKIT[/bold bright_cyan]\n"
                "[dim]Download • Clean • Compile • Convert[/dim]",
                border_style="bright_blue"
            )
        )

        console.print(
            "[yellow]⚠ Ignore warnings from underlying libraries. "
            "Most are harmless.[/yellow]"
        )

        console.print()


    def show_menu(self):

        table = Table(
            title="[bold cyan]Main Menu[/bold cyan]",
            box=box.ROUNDED,
            header_style="bold cyan"
        )

        table.add_column(
            "Option",
            justify="center",
            width=8
        )

        table.add_column("Action")

        table.add_row(
            "1",
            "📥 Download chapters"
        )

        table.add_row(
            "2",
            "🧹 Clean downloaded files"
        )

        table.add_row(
            "3",
            "📚 Compile into EPUB"
        )

        if PDF_AVAILABLE:

            pdf_text = (
                "[green]📄 Convert EPUB into PDF[/green]"
            )

        else:

            pdf_text = (
                "[red]📄 Convert EPUB into PDF (Unavailable)[/red]"
            )

        table.add_row(
            "4",
            pdf_text
        )

        table.add_row(
            "5",
            "🚪 Exit"
        )

        console.print(table)


    def pause(self):

        Prompt.ask(
            "\n[dim]Press Enter to continue[/dim]",
            default=""
        )


    def run(self):

        while True:

            console.clear()

            self.show_header()
            self.show_menu()

            choice = Prompt.ask(
                "[bold cyan]Choose an option[/bold cyan]",
                choices=["1", "2", "3", "4", "5"]
            )

            try:

                #
                # Download
                #
                if choice == "1":

                    console.print(
                        Panel(
                            "[green]Download Chapters[/green]",
                            title="📥",
                            border_style="green"
                        )
                    )

                    self.downloader.run()

                #
                # Clean
                #
                elif choice == "2":

                    console.print(
                        Panel(
                            "[green]Clean Downloaded Files[/green]",
                            title="🧹",
                            border_style="green"
                        )
                    )

                    self.cleaner.run()

                #
                # Compile
                #
                elif choice == "3":

                    console.print(
                        Panel(
                            "[green]Compile EPUB[/green]",
                            title="📚",
                            border_style="green"
                        )
                    )

                    self.compiler.run()

                #
                # PDF
                #
                elif choice == "4":

                    if not PDF_AVAILABLE:

                        console.print(
                            Panel(
                                "[red]PDF conversion unavailable[/red]\n\n"
                                "Install GTK Runtime:\n\n"
                                "https://github.com/tschoonj/"
                                "GTK-for-Windows-Runtime-Environment-Installer/releases",
                                title="❌ PDF Error",
                                border_style="red"
                            )
                        )

                    else:

                        console.print(
                            Panel(
                                "[green]Convert EPUB → PDF[/green]",
                                title="📄",
                                border_style="green"
                            )
                        )

                        self.converter.run()

                #
                # Exit
                #
                elif choice == "5":

                    console.print()

                    console.print(
                        Panel.fit(
                            "[bold green]👋 Goodbye![/bold green]\n"
                            "[dim]Thanks for using Webnovel Toolkit[/dim]",
                            border_style="green"
                        )
                    )

                    break


            except KeyboardInterrupt:

                console.print()

                console.print(
                    Panel(
                        "[yellow]Operation cancelled.[/yellow]",
                        title="⚠ Interrupted",
                        border_style="yellow"
                    )
                )


            except Exception as e:

                console.print()

                console.print(
                    Panel(
                        str(e),
                        title="❌ Unexpected Error",
                        border_style="red"
                    )
                )


            self.pause()


if __name__ == "__main__":

    MainController().run()