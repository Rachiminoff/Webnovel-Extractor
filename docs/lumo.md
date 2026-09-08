# Lumo Stories Scraper

## Why Lumo needs a dedicated scraper

Lumo Stories is a JavaScript-heavy application. The initial HTML response may not contain the complete chapter list, so a simple Requests + BeautifulSoup scraper is unreliable.

The Lumo scraper therefore uses a layered approach.

## Chapter discovery

For a table-of-contents URL such as:

```text
https://lumostories.com/en/story/211/chapters/
```

the scraper derives the story information and searches for chapter routes matching the site's read pattern.

### Strategy 1: rendered DOM links

Playwright loads the page and the scraper examines rendered links after the application has had time to populate the interface.

### Strategy 2: captured JSON responses

While the page loads, the scraper listens for JSON responses. Chapter data can sometimes be present in application API responses even when it is difficult to identify from the visible DOM.

### Strategy 3: rendered HTML and application data

The final rendered HTML is searched for chapter-route patterns and data embedded by the frontend.

### Lazy-loading support

The scraper scrolls the chapter list because some applications do not render every item until it enters the viewport.

## Content extraction

Individual chapter pages are loaded in Playwright. The scraper looks for likely content containers rather than assuming one permanent CSS class will exist forever.

Candidates are evaluated using characteristics such as:

- Amount of meaningful text.
- Paragraph count.
- Link density.
- Semantic HTML elements.
- Known site-specific containers.

## Failure diagnostics

If chapter discovery fails, the scraper saves diagnostic artifacts under:

```text
Downloads/fan_tl_chapters/debug/
```

These can include:

- Rendered HTML.
- Full-page screenshots.
- Additional response information.

Inspect these files before changing selectors blindly.

## Maintenance note

Scrapers break when websites change, especially client-rendered sites. The preferred response is not to pile increasingly specific selectors into unrelated code; instead, add or improve an isolated strategy in the site's dedicated scraper.
