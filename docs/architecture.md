# Architecture

## Design goal

The application should separate **site-specific knowledge** from the general workflow of downloading, cleaning, and compiling chapters.

A scraper should answer questions such as:

- How are chapters discovered on this site?
- Which URLs represent individual chapters?
- How is the page rendered?
- Where is the actual chapter content?

The rest of the application should not need to know those details.

## Current structure

```text
main.py
   │
   ├── downloader.py
   │      ├── Static site workflow
   │      ├── YoruApp workflow
   │      ├── Foxaholic workflow
   │      ├── Blogspot workflow
   │      └── Lumo adapter/service calls
   │
   ├── scrapers/sites/lumo.py
   │      ├── Chapter discovery
   │      ├── JSON response inspection
   │      ├── DOM fallback discovery
   │      ├── Content detection
   │      └── Debug artifact generation
   │
   ├── Cleaner.py
   │      ├── Generic cleanup
   │      └── Site-specific artifact cleanup
   │
   ├── compiler.py
   └── converter.py
```

## Why multiple strategies matter

A selector such as:

```python
page.wait_for_selector("div.prose")
```

works only while the website keeps exactly that structure. A site redesign can break a scraper even when the chapter data itself is still available.

A more resilient scraper instead uses a sequence of strategies:

1. Known site structure.
2. Semantic or route-based detection.
3. Application/network data.
4. Generic DOM heuristics.
5. Debug output for manual investigation.

## Future direction

The remaining site implementations can gradually move into `components/scrapers/sites/` using the same model. This should make `downloader.py` increasingly focused on orchestration rather than containing every site's scraping implementation.
