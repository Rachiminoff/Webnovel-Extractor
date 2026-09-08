# Webnovel Extractor

A modular command-line utility for downloading, cleaning, and compiling web novel chapters. The project supports plain HTML sites and JavaScript-heavy sites through site-specific scrapers with browser-based fallbacks.

> **Important:** Use this tool responsibly. Respect copyright, website terms, and the work of original authors and translators. Support official releases whenever available.

## Supported download modes

| Mode | Site / type | Approach |
|---|---|---|
| 1 | Static HTML | Requests + BeautifulSoup |
| 2 | YoruApp | Playwright-rendered browser scraping |
| 3 | Foxaholic | Browser-assisted scraping |
| 4 | Blogspot | Browser-assisted scraping |
| 5 | Lumo Stories | Network/API discovery + DOM fallbacks |

### Lumo Stories support

Lumo Stories uses a client-rendered interface, so the scraper uses multiple discovery strategies rather than trusting a single selector:

1. Render the chapter list in a Playwright browser.
2. Collect chapter URLs matching the site's `/read/` route pattern.
3. Inspect captured JSON responses for chapter information.
4. Search rendered HTML and inline application data as additional fallbacks.
5. Scroll through the page to trigger lazy-loaded chapter lists.
6. Save debug artifacts when discovery fails.

A result of zero chapters is treated as a failure rather than a successful download.

See [docs/lumo.md](docs/lumo.md) for implementation details.

## Cleaning

Downloaded chapters can contain site UI artifacts, watermarks, notices, and duplicated content. The cleaner provides:

- Legacy and universal cleaning modes.
- Generic removal of common ads, notices, social links, and footer content.
- Lumo-specific removal of artifacts such as `svg0`, `svg0 (icon)`, and the Lumo reproduction notice.
- Duplicate paragraph removal.
- Chapter-title normalization and XHTML output.

See [docs/cleaning.md](docs/cleaning.md) for details.

## Architecture

```text
Webnovel-Extractor/
├── main.py
├── components/
│   ├── downloader.py          # Main download coordinator and existing adapters
│   ├── Cleaner.py             # Chapter cleaning pipeline
│   ├── compiler.py            # EPUB compilation
│   ├── converter.py           # EPUB/PDF conversion
│   └── scrapers/
│       └── sites/
│           └── lumo.py        # Dedicated Lumo scraper
├── docs/
│   ├── architecture.md
│   ├── lumo.md
│   ├── cleaning.md
│   └── troubleshooting.md
└── README.md
```

The goal is to keep site-specific scraping logic separate from the general application workflow so a redesign on one website does not require rewriting the whole downloader.

## Requirements

- Python 3.7+ (Python 3.10+ recommended)
- Playwright
- Requests
- BeautifulSoup4
- EbookLib
- WeasyPrint
- lxml
- Rich

Install Python dependencies:

```bash
pip install requests beautifulsoup4 playwright ebooklib weasyprint lxml rich
playwright install
```

### Optional tools

- [Calibre](https://calibre-ebook.com/download) for ebook workflows.
- [Pandoc](https://pandoc.org/install.html) for document conversion workflows.

## Running the application

```bash
python main.py
```

Choose the appropriate download type and provide either a table-of-contents URL or the relevant chapter URL when prompted.

## Output folders

By default, the project uses folders under your system Downloads directory:

```text
fan_tl_chapters/       Raw downloaded chapters
fan_tl_chapters/debug/ Debug HTML, screenshots, and diagnostics
fan_tl_markdown/       Cleaned XHTML chapters
output/                Compiled EPUB or other output files
```

## Debugging scraper failures

Website structures change. When a supported scraper cannot discover or extract content, check the debug directory first. The saved HTML and screenshots show what the browser actually received and are more useful than guessing at a website's current structure.

See [docs/troubleshooting.md](docs/troubleshooting.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Lumo Stories scraper](docs/lumo.md)
- [Cleaning pipeline](docs/cleaning.md)
- [Troubleshooting](docs/troubleshooting.md)

## Contribution

Contributions are welcome. When adding support for a new website, prefer a dedicated site adapter and multiple extraction strategies over scattering new selectors throughout the application.
