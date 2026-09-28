# Architecture

This document explains how Webnovel Extractor is organized. It is written for maintainers who may need to add a website, change the CLI, or troubleshoot a failure.

## Design goal

The application has three major responsibilities:

1. **User interaction** — menus, prompts, progress, and messages.
2. **Workflow management** — configuration, jobs, retries, output paths, and results.
3. **Website extraction** — finding chapters and reading chapter content.

These responsibilities are kept separate so that a change in one area does not unnecessarily change another.

## High-level flow

```text
┌──────────────────────┐
│       CLI / UI       │
│      cli/ui.py       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Application layer  │
│  main.py + core/     │
│ config / jobs /      │
│ registry / logging   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Source adapters    │
│ components/downloader│
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Site-specific logic  │
│ Lumo / Yoru / etc.   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ XHTML chapter files  │
└──────────────────────┘
```

## `main.py`

`main.py` starts the application and coordinates the high-level workflows.

It should contain application flow, not website-specific scraping selectors.

The main menu currently provides:

- Download
- Clean
- Build EPUB
- Convert PDF
- Settings
- Diagnostics
- Sources

## `cli/ui.py`

This module contains reusable Rich UI behavior:

- headers;
- menus;
- prompts;
- status messages;
- summaries;
- friendly error conversion.

The purpose is consistency. A scraper should not need to know how a terminal panel or menu is drawn.

## `core/config.py`

The configuration layer stores user preferences and calculates workspace paths.

The default workspace is:

```text
~/Downloads/webnovel-toolkit/
```

with these subdirectories:

```text
chapters/
cleaned/
ebooks/
pdf/
logs/
```

Configuration is stored in:

```text
~/.webnovel-toolkit/config.json
```

## `core/registry.py`

The registry is the bridge between the CLI and website implementations.

It records information such as:

- source key;
- display name;
- description;
- whether a browser is required;
- the extractor instance.

The main menu therefore does not need a hard-coded branch for every website.

### Lumo exception

Lumo has a mature browser-managed bulk workflow. The registry exposes that workflow through a dedicated compatibility method instead of forcing Lumo through the generic chapter-by-chapter job loop.

This is important because browser lifecycle can affect JavaScript-heavy sites.

## `core/jobs.py`

The job layer handles generic download concerns:

- creating output directories;
- chapter numbering;
- existing-file checks;
- retries;
- progress reporting;
- success/failure/skipped counts;
- collecting errors.

It should not contain selectors for a specific website.

## `components/downloader/base.py`

This defines the shared extractor interface.

A normal extractor provides methods equivalent to:

```text
extract_chapters(table_of_contents_url)
extract_content(chapter_url, chapter)
get_output_filename(chapter)
```

This gives different websites a common shape without requiring them to use identical scraping techniques.

## `components/downloader/sites/`

This directory contains adapters for conventional supported sources such as Static HTML, YoruApp, Foxaholic, and Blogspot.

## `components/scrapers/sites/lumo.py`

Lumo has its own dedicated scraper because it is a JavaScript-heavy application.

The Lumo scraper handles:

- route-based chapter discovery;
- network JSON inspection;
- rendered DOM discovery;
- rendered HTML fallback;
- lazy-loading support;
- dynamic chapter-content detection;
- debug artifact creation;
- browser-managed bulk downloading.

## Failure isolation

A key architectural rule is:

```text
Website-specific problem
        ↓
Website-specific scraper
```

rather than:

```text
Website-specific problem
        ↓
Generic downloader rewrite
        ↓
Every website changes behavior
```

This is especially important for browser-based sites.

## Adding a source

For a new source:

1. Create a dedicated extractor or scraper.
2. Implement the common extractor interface where appropriate.
3. Register it in `core/registry.py`.
4. Declare browser requirements accurately.
5. Test discovery and content extraction separately.
6. Avoid modifying generic download logic unless the behavior is genuinely generic.

## Testing philosophy

When changing a scraper, test at least:

- one table-of-contents page;
- one normal chapter;
- one chapter near the beginning;
- one chapter near the end;
- a chapter known to behave differently, if one exists;
- the generated XHTML.

For JavaScript-heavy sites, keep debug HTML and screenshots from failed pages.


## Session download memory

The CLI keeps an in-memory record of discovered chapter links for a source and table-of-contents URL. Re-entering the same TOC during the same session reuses that list instead of rediscovering it. This state is deliberately not persisted to disk.

The download job then compares expected chapter filenames with the workspace. Existing, non-empty files are reported as skipped. This allows an interrupted download to be resumed without re-downloading completed chapters.
