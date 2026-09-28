# Webnovel Extractor

Webnovel Extractor is a command-line toolkit for downloading web novel chapters, cleaning the downloaded pages, building EPUB books, and converting EPUB files to PDF.

It is designed for people who want a straightforward workflow without having to understand how websites are built. Behind the scenes, the program uses different extraction methods for different kinds of websites, including ordinary HTML pages and JavaScript-heavy readers.

> **Use this tool responsibly.** Only download material you are legally allowed to access. Respect website terms of service, copyright, authors, translators, and publishers. When an official release is available, support it whenever possible.

---

## What the toolkit does

The application is organized as a simple production workflow:

```text
Download chapters
      ↓
Clean the downloaded files
      ↓
Build an EPUB
      ↓
Optionally convert the EPUB to PDF
```

You can stop after any stage. For example, you can download chapters and keep the XHTML files without creating an ebook.

### Main features

- Interactive terminal interface built with Rich.
- Multiple website-specific downloaders.
- Browser-based extraction for JavaScript-heavy sites.
- Lumo Stories support with bounded route, network, and rendered-DOM discovery.
- Automatic retry for supported generic download jobs.
- Existing-file detection to avoid unnecessary downloads.
- Persistent settings.
- Organized workspace folders.
- Cleaning of common website UI, advertisements, notices, and duplicate text.
- EPUB creation through Pandoc, Calibre, or EbookLib.
- EPUB-to-PDF conversion through WeasyPrint.
- Diagnostics for Python packages, browser support, and external tools.
- Debug HTML, screenshots, and response information when a scraper cannot find content.
- Application logging for troubleshooting.

---

## Supported sources

The current source registry includes:

| Source | Browser | General method | Notes |
|---|---:|---|---|
| Static HTML | No | Requests + HTML parsing | Intended for conventional chapter pages. |
| YoruApp | Yes | Playwright | Uses a rendered browser page. |
| Foxaholic | Yes | Browser-assisted | Uses browser rendering where required. |
| Blogspot | Yes | Browser-assisted | Handles Blogspot-style chapter pages. |
| Lumo Stories | Yes | Route + network + DOM discovery | Uses a dedicated resilient scraper. |

Website support is not a guarantee that every page will work forever. Websites can change their HTML, APIs, URLs, access rules, or reader design at any time.

---

# Installation

## 1. Install Python

Python **3.10 or newer is recommended**.

Check your installed version:

```bash
python --version
```

On some Windows installations, you may need:

```bash
py --version
```

If Python is not installed, install it from the official Python website and make sure the Python launcher or `python` command is available in your terminal.

## 2. Open the project folder

In Windows PowerShell or Command Prompt:

```powershell
cd C:\path\to\Webnovel-Extractor
```

Replace the path with the location where you extracted the project.

## 3. Create a virtual environment (recommended)

A virtual environment keeps this project's Python packages separate from other Python projects.

```powershell
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or in Command Prompt:

```cmd
.venv\Scripts\activate
```

When activated, your terminal normally shows `(.venv)` before the command prompt.

## 4. Install Python packages

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 5. Install Playwright browsers

Several supported sources require a real browser because their content is created by JavaScript.

Run:

```bash
python -m playwright install
```

If you only need Chromium, you can install that browser instead:

```bash
python -m playwright install chromium
```

## 6. Check the installation

Start the program:

```bash
python main.py
```

From the main menu, open **Diagnostics**. It shows which required Python packages, browser support, and optional external tools are available.

---

# Running the application

Start the application with:

```bash
python main.py
```

The main menu provides these workflows:

```text
1  Download       Discover and download chapters
2  Clean          Remove website noise and normalize XHTML
3  Build EPUB     Create an ebook from cleaned chapters
4  Convert PDF    Convert an EPUB into PDF
5  Settings       Change workspace and retry settings
6  Diagnostics    Check dependencies and storage
7  Sources        View registered website extractors
0  Exit           Close the application
```

You do not need to use every feature. A common workflow is:

```text
Download → Clean → Build EPUB
```

PDF conversion is optional.

---

# Downloading chapters

Choose **Download** from the main menu.

You will first select a source, such as Lumo Stories or YoruApp. The program then asks whether you want to download a whole series or a single chapter.

## Bulk download

Choose **Bulk download** when you have a table-of-contents or chapter-list URL.

For example:

```text
Table of Contents URL: https://example.com/story/123/chapters/
Start chapter number [1]: 1
```

The program will:

1. Open the table-of-contents page.
2. Discover chapter links using the selected source's extraction method.
3. Start downloading from the chapter number you selected.
4. Save each chapter as XHTML.
5. Report successful, skipped, and failed chapters.

### Start chapter number

The start number controls the number assigned to the first chapter saved by the download operation. For normal ascending numbering, the next discovered chapters continue upward.

For example, if you enter:

```text
Start chapter number [1]: 50
```

the first downloaded chapter is numbered `50`, the next `51`, and so on.

For Lumo, you can also use a descending sequence when the discovered TOC is newest-first. For example, with 236 discovered chapters, entering `236` numbers them `236`, `235`, `234`, down to `001`. This follows the discovered TOC order.

## Single chapter

Choose **Single chapter** when you already have the direct URL of one chapter.

The program processes that chapter without first discovering the entire table of contents.

---

# Download behavior

## Existing files

The downloader checks whether the expected chapter file already exists and contains data. If it does, the chapter is skipped instead of being downloaded again.

This is useful when a large download was interrupted and you want to continue without starting from the beginning. It is also useful when you run the same table of contents again after adding new chapters.

### Remembered table of contents

During a single program session, the toolkit remembers the chapter list it discovered for a source and table-of-contents URL. If you enter the same TOC again, it can reuse the chapter links instead of opening the TOC and discovering the same links again.

The remembered TOC is session-only. It is intentionally cleared when the program closes, so stale website data is not reused the next time the program starts.

When a remembered TOC is used, the downloader still checks the output folder. Already downloaded chapters are skipped, while missing chapters are downloaded normally.

## Retries

For downloaders using the generic job system, failed operations can be retried automatically.

The retry count can be changed under **Settings**.

A retry is useful for temporary problems such as:

- a slow connection;
- a temporarily unavailable page;
- a browser timeout;
- a short-lived server error.

Retries cannot fix a permanently changed website structure. If a site has changed its reader, the scraper itself may need an update.

## Lumo bulk downloading

Lumo Stories uses its own browser-managed bulk download workflow. This is intentional.

Lumo's scraper keeps one browser session alive while processing the chapter list. The generic per-chapter job system must not replace that workflow because doing so can change how the Lumo reader behaves.

---

# Lumo Stories

Lumo Stories uses a JavaScript-rendered reader. A simple HTTP request may therefore return only part of the page instead of the chapter list or chapter text.

The dedicated Lumo scraper uses several strategies.

## Chapter discovery

For a table-of-contents URL such as:

```text
https://lumostories.com/en/story/199/chapters/
```

the scraper can use:

1. Known `/story/<id>/read/<chapter-id>/` URL patterns.
2. Links found in the rendered browser page.
3. JSON responses captured while the page loads.
4. Chapter information stored inside application data.
5. Rendered HTML as a final fallback.
6. Page scrolling to trigger lazy-loaded chapter lists.

This is why a message such as:

```text
Found 236 Lumo chapter links.
```

is significant: it means the table-of-contents discovery stage succeeded.

## Chapter content extraction

Lumo chapter pages can take different amounts of time to finish rendering. The scraper therefore does not rely on one fixed short delay.

It waits for useful chapter text and checks several possible content containers. The current content search can wait up to approximately 15 seconds for the reader to become usable.

This approach is more reliable than assuming that every chapter will finish loading after exactly the same amount of time.

## Debug files

If Lumo cannot identify chapter content, it saves diagnostic files under the chapter output directory's `debug` folder.

Depending on the failure, these can include:

- the rendered HTML;
- a screenshot of the page;
- JSON containing error information or captured response URLs.

For example:

```text
Downloads/
└── webnovel-toolkit/
    └── chapters/
        └── debug/
            ├── lumo_chapter_141_failed.html
            ├── lumo_chapter_141_failed.png
            └── ...
```

These files are useful when a chapter behaves differently from the others.

## Why one Lumo chapter can fail while another works

A chapter list can be correct while individual chapters behave differently. Possible reasons include:

- the reader loads at a different speed;
- the chapter contains an unusual element;
- the site returned an incomplete page;
- the site's JavaScript application behaved differently for that request;
- the chapter uses a slightly different DOM structure;
- the site temporarily blocked or interrupted the request.

If only a few chapters fail, compare their debug HTML and screenshots with a nearby chapter that works before changing the scraper.

---

# Cleaning chapters

Downloaded chapter files are not always ready to put directly into an ebook.

A website can add things such as:

- navigation controls;
- advertisements;
- social links;
- watermarks;
- copyright notices;
- repeated titles;
- decorative icons;
- empty HTML wrappers;
- duplicate paragraphs.

The **Clean** workflow processes the downloaded HTML/XHTML files and writes cleaned XHTML files to the `cleaned` workspace folder.

The cleaner contains both general cleanup rules and targeted rules for known site artifacts.

## Why cleanup is separate from downloading

Keeping download and cleaning as separate stages has an important advantage: the original downloaded files remain available for inspection.

If a cleaning rule removes something incorrectly, you can adjust the cleaner and process the original files again without downloading the entire series.

See [docs/cleaning.md](docs/cleaning.md) for the detailed cleaning pipeline.

---

# Building an EPUB

After cleaning your chapters, choose **Build EPUB**.

The compiler looks for XHTML files in the cleaned workspace.

You can choose one of three EPUB engines:

### Pandoc

Pandoc is a command-line document conversion tool. It is useful when you already have Pandoc installed and want an external conversion engine.

### Calibre

Calibre provides `ebook-convert`, which can convert HTML/XHTML content into ebook formats and is useful if Calibre is already part of your ebook workflow.

### EbookLib

EbookLib is a Python library used to construct EPUB files directly from Python.

The application checks whether the selected engine is available before starting the compilation.

## EPUB metadata

The compiler asks for book information such as:

- title;
- author;
- language;
- output filename;
- optional cover image.

If you provide a cover image URL, the compiler can download the image and include it in the ebook.

---

# Converting EPUB to PDF

Choose **Convert PDF** after you have an EPUB file.

The PDF converter uses **WeasyPrint**.

You can convert:

- one EPUB file; or
- a folder containing multiple EPUB files.

The converter also provides an option for treating cover or illustration pages as full-page images.

## WeasyPrint requirement

WeasyPrint is a Python package, but it also depends on platform libraries. On Windows, installing the Python package alone may not always be enough.

If Diagnostics reports that WeasyPrint is unavailable, follow the WeasyPrint installation instructions for your operating system rather than assuming that `pip install weasyprint` is sufficient.

---

# Workspace and files

The default workspace is:

```text
C:\Users\<YourName>\Downloads\webnovel-toolkit\
```

The exact location depends on your Windows user account and operating system.

The workspace is organized as follows:

```text
webnovel-toolkit/
├── chapters/       Raw downloaded chapter XHTML files
├── cleaned/        Cleaned XHTML files ready for compilation
├── ebooks/         Generated EPUB files
├── pdf/            Generated PDF files
└── logs/           Application log files
```

Lumo-specific debugging files are stored under:

```text
chapters/debug/
```

## Changing the workspace

Open:

```text
Settings → Output directory
```

Choose another folder and the toolkit will create the required subdirectories there.

---

# Configuration

The application stores its settings separately from the project files:

```text
~/.webnovel-toolkit/config.json
```

On Windows this normally corresponds to a folder inside your user profile.

Current settings include:

| Setting | Purpose |
|---|---|
| `output_root` | Main workspace location. |
| `retries` | Number of retries after a failed generic download attempt. |
| `request_timeout` | Timeout used by request-based operations. |
| `browser_timeout` | General browser timeout setting. |
| `pause_between_retries` | Delay between retry attempts. |
| `show_timestamps` | Controls timestamp preference for application output/logging where supported. |

You normally do not need to edit the JSON file manually. Use the **Settings** menu whenever possible.

If the configuration becomes invalid, the safest approach is to close the program and remove or rename the configuration file so the application can create a fresh default configuration.

---

# Diagnostics

The **Diagnostics** screen is intended to answer a simple question:

> "Is my computer ready to perform this operation?"

It checks important components such as:

- Python;
- Requests;
- BeautifulSoup;
- Playwright;
- EbookLib;
- Rich;
- Pandoc;
- Calibre;
- WeasyPrint.

It also displays the current workspace locations.

If a feature is unavailable, check Diagnostics before troubleshooting the scraper itself.

For example:

```text
Playwright    ✓ Ready
EbookLib      ✓ Ready
Pandoc        — Not installed
Calibre       — Not installed
WeasyPrint    — Optional
```

This does not mean the entire program is broken. It means that features depending on those components may not be available.

---

# Logging

The application writes logs to:

```text
webnovel-toolkit/logs/
```

The log is intended for troubleshooting rather than normal use.

The terminal shows the important information in simple language. The log can contain more technical details that are useful when diagnosing a problem.

When reporting a bug, include:

1. the source you selected;
2. the URL or type of page involved;
3. the chapter number, if applicable;
4. the terminal error message;
5. the relevant log entry;
6. any generated debug HTML or screenshot.

Do not include private credentials, cookies, session tokens, or other sensitive information when sharing logs.

---

# Troubleshooting

## The program does not start

Run:

```bash
python --version
python -m pip install -r requirements.txt
```

Then run:

```bash
python main.py
```

If Python cannot find the command, use the Python launcher on Windows:

```cmd
py main.py
```

## Playwright is missing

Install the Python package:

```bash
python -m pip install playwright
```

Then install a browser:

```bash
python -m playwright install chromium
```

Open **Diagnostics** afterward.

## A source finds zero chapters

First make sure the URL works normally in a browser.

Then:

1. Check that you entered the site's table-of-contents URL rather than a random page.
2. Check the generated debug files.
3. Look at the saved HTML and screenshot.
4. Determine whether the site changed its chapter URL format or page structure.
5. Update the dedicated source scraper rather than changing the generic downloader.

A zero-chapter result should be treated as a discovery failure, not as a successful empty download.

## Lumo finds the chapters but some chapters fail

This means chapter discovery is probably working, but one or more individual reader pages could not be processed.

Check the debug files for the affected chapter.

For example, if chapters 140, 142, and 144 work but 141 does not, compare the debug screenshot and HTML for chapter 141 with a working chapter.

Possible causes include:

- the reader did not finish loading;
- a temporary server response;
- an unusual chapter layout;
- a site-side change;
- an access or blocking response.

The Lumo scraper already waits for useful content instead of relying on only one short fixed delay, but a website can still return a page that requires a new extraction strategy.

## A chapter downloads but contains website controls

Run the **Clean** workflow. The cleaner removes common reader artifacts and contains Lumo-specific rules for known controls and notices.

If an unwanted element remains, inspect the raw XHTML first. Do not immediately add a broad rule such as "delete every element containing the word icon," because legitimate chapter content can contain similar words.

## EPUB creation says Pandoc is missing

Install Pandoc and make sure the `pandoc` command is available from your terminal.

Then reopen the application and check Diagnostics.

## EPUB creation says Calibre is missing

Install Calibre and make sure the `ebook-convert` command is available.

Then reopen the application and check Diagnostics.

## PDF conversion is unavailable

Check WeasyPrint first. On some operating systems, WeasyPrint needs additional native libraries.

If the Python package is installed but the feature still fails, follow the official WeasyPrint platform installation instructions.

## The website changed

This is a normal maintenance issue for a web scraper. A website can change its HTML, CSS classes, API responses, URL structure, or JavaScript application without warning.

The preferred maintenance process is:

```text
Observe the failure
      ↓
Save/debug the page
      ↓
Identify what changed
      ↓
Update the site's scraper
      ↓
Leave generic downloader logic unchanged
```

This keeps site-specific changes from breaking unrelated sources.

---

# Project structure

The project separates the user interface, application workflow, and website-specific extraction logic.

```text
Webnovel-Extractor/
│
├── main.py                         Application entry point
├── requirements.txt                Python dependencies
├── LICENSE
├── README.md
│
├── cli/
│   └── ui.py                       Shared terminal UI components
│
├── core/
│   ├── config.py                   Persistent configuration
│   ├── jobs.py                     Download jobs and results
│   ├── logging_utils.py            Application logging
│   └── registry.py                 Registered website extractors
│
├── components/
│   ├── Cleaner.py                  Chapter cleaning
│   ├── compiler.py                 EPUB compilation
│   ├── converter.py                EPUB-to-PDF conversion
│   │
│   ├── downloader/
│   │   ├── __init__.py             Downloader public API
│   │   ├── base.py                 Shared extractor interfaces
│   │   ├── core.py                 Download coordination
│   │   └── sites/                   Site-specific generic adapters
│   │       ├── blogspot.py
│   │       ├── foxaholic.py
│   │       ├── static.py
│   │       └── yoru.py
│   │
│   └── scrapers/
│       ├── core/                    Browser/content/debug helpers
│       └── sites/
│           └── lumo.py              Dedicated Lumo scraper
│
└── docs/
    ├── architecture.md             Technical architecture
    ├── cleaning.md                  Cleaning rules and design
    ├── lumo.md                     Lumo-specific behavior
    └── troubleshooting.md          Maintenance and troubleshooting
```

## Why the project is structured this way

The main application should not need to know how every website works.

Instead:

```text
CLI
 ↓
Job / workflow layer
 ↓
Registered source adapter
 ↓
Website-specific scraper
 ↓
Chapter files
```

This makes it possible to improve the terminal interface without rewriting the Lumo scraper, and to update one website's scraper without changing every other downloader.

---

# Adding a new website

A new website should normally have its own extractor or scraper.

At a high level, it should provide:

1. a source name;
2. a description;
3. a chapter-discovery method;
4. a chapter-content extraction method;
5. an output filename method when the default is not sufficient.

Browser-based sites should declare that they require a browser.

Avoid putting website-specific selectors or special cases into generic downloader code. If a website changes, its dedicated adapter should be the first place to look.

For difficult JavaScript sites, prefer multiple independent signals such as:

- known routes;
- rendered links;
- network responses;
- embedded application data;
- semantic DOM elements.

A scraper that depends on one CSS class is much more likely to break after a redesign.

---

# Responsible use

This project is a technical tool, not a license to redistribute copyrighted material.

You are responsible for making sure your use of the tool is lawful and permitted. In particular:

- do not bypass access controls;
- do not redistribute copyrighted works without permission;
- respect website terms and reasonable access limits;
- respect authors and translators;
- avoid unnecessary traffic to websites;
- support official releases where available.

The fact that a page can technically be downloaded does not mean that downloading or redistributing it is legally permitted.

---

# Development and maintenance

Before changing a scraper:

1. reproduce the problem;
2. identify whether discovery or content extraction failed;
3. inspect the debug output;
4. make the smallest site-specific change that fixes the problem;
5. test a working chapter and a previously failing chapter;
6. run Python compilation/import checks before packaging a release.

The most important maintenance rule is simple:

> **Do not replace a working site's extraction logic merely to improve the user interface.**

The CLI, job system, registry, and scraper should remain separate so improvements to one layer do not silently change the behavior of another.

---

# License

See [LICENSE](LICENSE) for the project's license terms.
