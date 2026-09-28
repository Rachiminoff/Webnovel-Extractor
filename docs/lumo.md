# Lumo Stories Scraper

Lumo Stories is treated as a dedicated source because its reader is heavily dependent on JavaScript. The chapter list and chapter text may not be present in the initial HTML response.

## What the scraper is trying to do

The Lumo scraper has two separate jobs:

1. discover the chapters in a story;
2. open each chapter and extract the actual chapter text.

Keeping these stages separate is useful when diagnosing problems.

---

## Chapter discovery

A typical table-of-contents URL looks like:

```text
https://lumostories.com/en/story/199/chapters/
```

The scraper first extracts the story ID from the URL. It then opens the page in Chromium through Playwright.

### Strategy 1: known chapter routes

The scraper first looks for chapter URLs that follow Lumo's known reader pattern. This is the fastest route when the page exposes those links directly.

Lumo chapter URLs currently follow a pattern similar to:

```text
/en/story/<story-id>/read/<chapter-id>/
```

These routes are treated as a strong signal because they identify actual chapter pages rather than relying on the visible text of a chapter card.

### Strategy 2: rendered links

The scraper examines links after the page has been rendered. The chapter links are collected in a single browser-side pass rather than opening each link or card one at a time. This keeps large tables of contents responsive.

### Strategy 3: captured JSON

While the page loads, the scraper observes JSON responses. If chapter information is returned by the site's application API, the scraper can inspect that data.

### Strategy 4: rendered HTML and application data

If the previous methods do not find chapters, the final rendered page is searched for chapter routes and embedded data.

### Lazy-loaded chapter lists

Some chapter lists are loaded only after the page is scrolled. The scraper performs a small, bounded scroll pass to give these entries an opportunity to appear. Discovery is deliberately time-bounded so a slow or changed page does not leave the CLI waiting indefinitely.

### Discovery timeouts

The story page is loaded with a bounded timeout. If the initial navigation takes too long, the scraper can continue with whatever content was successfully rendered instead of waiting indefinitely. The same principle is used for the later discovery steps.

### Duplicate removal

The same chapter can sometimes be exposed through more than one discovery method. Duplicate URLs are removed before downloading.

### Chapter titles

Lumo chapter cards contain more than just the chapter title. A card may also contain information such as:

```text
Last updated: 1 year ago • 2,148 words Read
```

The scraper removes this metadata before choosing a title. It also ignores interface labels such as `Read`, `Open`, and `Continue`. The goal is to preserve the actual chapter title instead of saving the card's metadata or a generic label such as `Chapter 1`.

If a reliable title cannot be found, the scraper uses a numbered fallback rather than saving unrelated page text.

---

## Chapter content extraction

A chapter page can finish rendering at different speeds. A fixed delay such as "always wait 1.5 seconds" is therefore unreliable.

The scraper instead:

1. opens the chapter in Chromium;
2. waits for the document to begin loading;
3. checks several possible content containers;
4. measures the amount of useful text and paragraph structure;
5. waits and checks again if the reader is not ready;
6. continues until useful content is found or the approximately 15-second content-search limit is reached.

The scraper considers candidates such as:

```text
article
main article
[data-testid*=chapter]
[data-testid*=content]
[class*=chapter-content]
[class*=reader]
[class*=prose]
main
```

The exact selector is not treated as the only source of truth. A candidate is scored using the amount of text, paragraph count, link density, and other signals.

This is intended to survive small changes to the reader layout.

---

## Cleaning the chapter DOM

The Lumo reader can contain interface elements inside or around the same container as the chapter prose.

Before the XHTML is saved, the scraper removes known interface elements such as:

- decorative SVG elements;
- buttons;
- form controls;
- horizontal separators;
- empty icon wrappers;
- known icon/counter remnants.

The general cleaning stage performs another defensive cleanup later. This means the downloader does not need to make every final formatting decision itself.

---

## Browser lifecycle

Lumo bulk downloads intentionally use one browser context for the whole download run.

This is important.

The generic job layer normally thinks in terms of individual chapter operations. Lumo's proven implementation, however, manages its browser session internally. Replacing it with a new browser context for every chapter can change timing and page behavior.

For this reason, the registry can expose a dedicated legacy/bulk workflow for Lumo while the rest of the application still uses the modern job system.

This is a compatibility boundary, not a sign that the old implementation should be removed immediately.

---

## Debug files

When Lumo cannot find the chapter body, the scraper saves diagnostics in:

```text
<workspace>/chapters/debug/
```

Examples include:

```text
lumo_toc_failed.html
lumo_toc_failed.png
lumo_chapter_141_failed.html
lumo_chapter_141_failed.png
lumo_chapter_141_error.html
lumo_chapter_141_error.png
```

Depending on the failure, a JSON file may also contain captured response URLs or error details.

### What the files mean

**HTML**

Shows what the browser received after JavaScript rendering. This is often the most useful file for determining whether the website changed its structure.

**PNG screenshot**

Shows what the reader looked like when extraction failed. This is useful when the page is blocked, stuck on a loading screen, redirected, or displaying an unexpected prompt.

**JSON**

Provides technical information such as the URL being processed, the exception message, or captured response URLs.

---

## Diagnosing a single failed chapter

Suppose the terminal says:

```text
Downloading Lumo chapter 141/236
Could not identify chapter content; debug files were saved.
```

That tells you something important: chapter discovery worked, but the content stage did not find enough usable text.

The recommended process is:

1. Open the debug screenshot.
2. Check whether the chapter reader actually loaded.
3. Open the debug HTML and search for the chapter prose.
4. Compare it with a nearby chapter that downloaded successfully.
5. Determine whether the difference is timing, access, or HTML structure.
6. Only then change the scraper.

If the prose is clearly present in the saved HTML but the scraper still cannot select it, the content-candidate scoring should be improved.

If the prose is not present at all, changing selectors may not help. The browser may have received a different response.

---

## Maintenance guidance

Avoid replacing the whole Lumo scraper because one chapter fails.

Prefer small, isolated changes such as:

- adding a new candidate selector;
- improving the candidate score;
- recognizing a new route pattern;
- handling a newly observed API response;
- adding a narrowly targeted cleanup rule.

After a change, test both a chapter that previously worked and a chapter that previously failed.


## Resuming an interrupted Lumo download

Lumo downloads can be resumed safely. Before opening Chromium, the downloader checks for existing `chNNN.xhtml` files in the chapter workspace. A non-empty file is treated as already downloaded and is skipped.

If the same Lumo TOC is entered again during the same application session, the toolkit also reuses the chapter links it already discovered. It does not need to rediscover the TOC unless the URL or source changes.

This session memory is temporary and disappears when the application closes. The chapter files themselves remain on disk, so a later session can still skip files that were already completed.

### Starting from a descending chapter number

For sources whose discovered table of contents is ordered from newest to oldest, you can enter the highest chapter number as the starting number. The downloader then decreases the number for each discovered entry.

For example, with 236 discovered chapters and a starting number of `236`, the assigned filenames are:

```text
ch236.xhtml
ch235.xhtml
ch234.xhtml
...
ch002.xhtml
ch001.xhtml
```

This numbering follows the order in which the source's chapter links were discovered. If the starting number is too small to number all discovered chapters, the downloader stops rather than creating zero or negative chapter numbers.
