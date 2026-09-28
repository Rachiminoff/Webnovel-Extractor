# Troubleshooting

This guide is intended to help identify **where** a failure occurs before changing code.

The toolkit has several stages:

```text
Website discovery
      ↓
Chapter download
      ↓
Cleaning
      ↓
EPUB compilation
      ↓
PDF conversion
```

The first useful question is therefore:

> Which stage failed?

---

## The program does not start

Check Python:

```bash
python --version
```

Then install the project requirements:

```bash
python -m pip install -r requirements.txt
```

On Windows, you can also try:

```cmd
py main.py
```

If the project uses a virtual environment, activate it before starting the program.

---

## Playwright errors

Browser-based sources need Playwright and a browser installation.

Install the Python package:

```bash
python -m pip install playwright
```

Install Chromium:

```bash
python -m playwright install chromium
```

Then run **Diagnostics** from the application.

---

## Zero chapters found

If the program reports zero discovered chapters, the failure happened during **chapter discovery**.

Check:

1. Is the URL a table-of-contents page?
2. Does the page open normally in a browser?
3. Does the website currently show a chapter list?
4. Did the site's chapter URL pattern change?
5. Are debug HTML and screenshots available?

Do not immediately change the generic downloader. A discovery failure normally belongs in the source-specific scraper.

---

## Chapters are discovered, but individual chapters fail

This is a different problem.

For example:

```text
Found 236 Lumo chapter links.
Downloading chapter 141...
Could not identify chapter content.
```

The discovery stage succeeded. The failure happened while reading the chapter page.

For Lumo, inspect the debug files for that chapter.

### If the screenshot shows a loading page

The page may not have finished rendering, or the site may be temporarily slow.

### If the screenshot shows a block or access message

The website may be refusing or changing the response for automated access.

### If the screenshot shows the chapter normally

Open the saved HTML. If the chapter prose is present, the scraper may need a new content candidate or scoring rule.

### If the screenshot and HTML do not contain the chapter

The problem is probably not a selector. The browser did not receive the expected content.

---

## Lumo `querySelectorAll` errors

An error such as:

```text
Page.evaluate: TypeError: Cannot read properties of undefined
(reading 'querySelectorAll')
```

usually means the JavaScript cleanup code was given an invalid DOM root.

The correct pattern for a Playwright locator is to evaluate on the locator itself rather than trying to pass the locator through `page.evaluate()`.

This is an implementation issue, not evidence that the Lumo website has necessarily changed.

---

## A Lumo chapter cannot be identified

If the terminal says:

```text
Could not identify chapter content; debug files were saved.
```

the scraper did not find a content container containing enough useful text within its content-search window.

Open the corresponding debug screenshot and HTML before making any code changes.

Remember that Lumo is dynamically rendered. Different chapters may take different amounts of time to become usable.

---

## A chapter contains reader controls or website notices

Run **Clean** after downloading.

The cleaner contains generic rules and Lumo-specific rules for known interface artifacts.

If something remains, compare the raw and cleaned files to determine whether the problem is extraction or cleaning.

---

## EPUB creation fails

### Pandoc

Check:

```bash
pandoc --version
```

If the command is not found, install Pandoc and make sure it is available in your PATH.

### Calibre

Check:

```bash
ebook-convert --version
```

If the command is not found, install Calibre and make sure its command-line tools are available.

### EbookLib

Check that the Python package is installed:

```bash
python -m pip install ebooklib
```

---

## PDF conversion fails

The PDF workflow uses WeasyPrint.

Check whether Python can import it:

```bash
python -c "import weasyprint; print(weasyprint.__version__)"
```

If that works but conversion still fails, check the WeasyPrint platform dependencies for your operating system.

---

## The workspace is in the wrong location

Use:

```text
Settings → Output directory
```

The application will create the required folders under the selected workspace.

---

## Configuration problems

The configuration file is:

```text
~/.webnovel-toolkit/config.json
```

If the configuration is damaged or contains an old setting, close the application and rename the file. On the next start, the toolkit will create a fresh default configuration.

---

## Where to find logs

Application logs are stored in:

```text
<workspace>/logs/
```

When reporting a problem, provide the relevant log section together with the terminal message.

Remove private information before sharing logs.

---

## Where to find Lumo debug files

Lumo-specific debug files are stored in:

```text
<workspace>/chapters/debug/
```

Useful files normally include:

- `.html` — rendered page source;
- `.png` — screenshot;
- `.json` — technical error or response information.

---

## Website redesigns

Websites change. A scraper can therefore break even when the extractor code has not been touched.

The recommended maintenance process is:

```text
Reproduce
   ↓
Identify the failing stage
   ↓
Inspect the actual page/debug files
   ↓
Update only the affected source
   ↓
Test working + failing examples
```

Avoid adding random selectors to the generic downloader. A website-specific change belongs in that website's adapter or scraper.

---

## When asking for help

Include:

- operating system;
- Python version;
- source name;
- URL type (table of contents or chapter);
- chapter number;
- terminal error;
- relevant log entry;
- relevant debug screenshot/HTML.

Do not include passwords, cookies, authentication headers, session tokens, or other private information.
