# Webnovel Extractor (FanTL Tool)

A utility tool for downloading, cleaning, and compiling web novel chapters, primarily from **YoruApp** and **WordPress-hosted** novel sites. Designed specifically to handle fan translations and dynamically loaded content with minimal setup.

---

## ⚠️ Important Notice

- This tool is **confirmed to work best on YoruApp/LumoStories** (a popular fan translation novel hosting platform) and **WordPress-based sites**.
- Functionality on other novel websites or platforms **may be limited or require custom adjustments**.
- Performance and reliability may vary outside these supported site types.
- Chapters downloaded from YoruApp are already clean and properly structured. You can skip the cleaning step and proceed directly to compilation.
- Always support the **original authors and official translations** whenever possible.

---

## Features

**Downloader**

- Enter a Table of Contents (TOC) URL for bulk downloads, or a single chapter URL.
- Choose download type:
  - **Static** – For sites serving plain HTML pages.
  - **Rendered** – For JavaScript-heavy sites like YoruApp (requires Playwright).

**Cleaner**

- Cleans downloaded chapters to remove extraneous content (ads, footers, translator notes).
- Supports two cleaning modes:
  - **Legacy**
  - **Universal** (recommended)

**Compiler**  
- Compiles cleaned chapters into EPUB format for offline reading convenience.

**EPUB to PDF Converter**

- Converts EPUB ebooks to clean, well-formatted PDFs with cover extraction, chapter breaks, embedded images, and page numbers for easy reading and printing.
---

## Requirements

- **Python 3.7+** (latest version recommended; Python 3.10+ preferred for best compatibility)
- **Playwright** – For scraping JavaScript-heavy sites like YoruApp
- **Requests** – For making HTTP requests
- **BeautifulSoup4** – For parsing and cleaning HTML
- **EbookLib** – For handling EPUB files (used in EPUB compilation and conversion)
- **WeasyPrint** – For converting HTML content to PDF (used in EPUB to PDF conversion)
- **Calibre** *(optional but recommended)* – For compiling to EPUB and other ebook formats
- **Pandoc** *(optional)* – Universal document converter used in some EPUB pipelines

## Install Python dependencies

```bash
pip install requests beautifulsoup4 playwright ebooklib weasyprint
playwright install

```

## Install EPUB tools

### Calibre 

Download from:  
https://calibre-ebook.com/download

Add to PATH if needed:

```bash
# Example for Windows
setx PATH "%PATH%;C:\Program Files\Calibre2"
```

### Pandoc 

Download from:  
https://pandoc.org/install.html

Add to PATH if needed:

```bash
# Example for Windows
setx PATH "%PATH%;C:\Program Files\Pandoc"
```
---

## 📁 Directory Structure
By default, the tool creates and uses these folders inside your system’s **Downloads** directory (e.g., `C:\Users\YourName\Downloads` on Windows or `/home/yourname/Downloads` on Linux/macOS). You can change the paths in the source code if needed.

```
fan_tl_chapters/     # Raw downloaded HTML/XHTML chapters  
fan_tl_markdown/     # Cleaned and processed XHTML chapters (ready for compilation)  
output/              # Compiled EPUBs
```

**Note:**  
- Make sure these folders exist or let the program create them automatically.  
- Keeping these directories organized helps separate raw data, cleaned content, and final compiled books for easier management.  
- If you change the default locations in the code, remember to update your workflow accordingly.

---

## ⚠️ Limitations and Known Issues

- The tool is tailored for **YoruApp and WordPress** sites — other platforms may require manual customization (selectors/scraping logic).
- **Playwright dependency** adds installation complexity.
- Large downloads may require a **stable internet connection** and **adequate system resources**.

---

## 🤝 Contribution & Support

- Feel free to open **issues** or **pull requests** to improve support for more sites or add features.
- Please use this tool responsibly and respect copyright laws.
- **Support original authors, fan, and official translators whenever possible!**
