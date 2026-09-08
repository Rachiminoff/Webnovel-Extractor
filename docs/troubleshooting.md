# Troubleshooting

## Zero chapters found

Do not treat this as a successful download.

For JavaScript-heavy sites:

1. Confirm the table-of-contents URL works in a normal browser.
2. Check the site's current chapter URL pattern.
3. Inspect `Downloads/fan_tl_chapters/debug/`.
4. Compare the saved HTML and screenshot with the scraper's discovery logic.
5. Update the dedicated site scraper rather than unrelated downloader code.

## Playwright problems

Install the browser dependencies:

```bash
playwright install
```

If the Python package is missing:

```bash
pip install playwright
```

## Chapter contains UI artifacts

Run the cleaner after downloading. If the artifact is site-specific, add a narrow rule that matches the exact unwanted text or element instead of using an overly broad pattern.

## Website redesigns

Website changes are expected to break scraping logic occasionally. The debug files are part of the maintenance workflow: inspect what the browser now sees, identify which strategy failed, and update that isolated strategy.

## A completely serious note about YoruApp

> **How many times does YoruApp want to change their website?** Don't they know that changing a UI users are already familiar with can be a bad move?

In fairness, redesigning a UI can be perfectly reasonable for accessibility, maintainability, performance, or new features. But from the perspective of someone maintaining a scraper, every redesign is another exciting opportunity to discover that a selector you trusted yesterday has become historical archaeology.

This is exactly why the project should move toward route-based, semantic, and data-based discovery instead of relying on one permanent CSS selector.
