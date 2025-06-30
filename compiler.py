import re
from pathlib import Path
from bs4 import BeautifulSoup

class ChapterCleaner:

    def run(self, mode=2):
        # Main entry point to clean all HTML files using the selected mode (default: 2 - universal cleaner)
        selected_mode = mode
        self.clean_all_html(mode=selected_mode)

    # Regex patterns for detecting intro and outro paragraphs that are commonly found in fan translations
    intro_patterns = [
        re.compile(r'^\s*(about|ko-fi|tips for lilies|planting a lily field|t/n|support|follow|master list)', re.I),
    ]

    outro_patterns = [
        re.compile(
            r'^\s*(tl note|tl;|t/n:|author[’\'s]* note|ramblings|finally posting|thank you for reading|support me|as for the reason|next chapter|previous chapter|read on|thoughts\?|follow me|ko-fi|patreon|buy me a coffee|share this|thoughts on|check out these other novels|comments|leave a comment)',
            re.I
        ),
    ]

    # Pattern to detect junk text that often appears as noise in fan translation posts
    junk_patterns = re.compile(
        r"(table of contents|toc|back to top|comment|reblog|ko-fi|t/n:|insidethemirror|please read at yuri translations|please read at jiulian lian|please read at .+?wordpress\.com)",
        re.I
    )

    def __init__(self, input_folder=None, output_folder=None):
        # Setup input and output folders, defaulting to Downloads/fan_tl_chapters and fan_tl_markdown
        downloads_path = Path.home() / "Downloads"
        self.input_folder = input_folder or downloads_path / "fan_tl_chapters"
        self.output_folder = output_folder or downloads_path / "fan_tl_markdown"
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.junk_patterns = ChapterCleaner.junk_patterns  # Assign class-wide regex for junk

    def select_mode(self):
        # Interactive mode selection between old and new cleaner logic
        print("Choose cleaning mode:")
        print("1. Hazevie's baihe cleaner (old logic)")
        print("2. Universal cleaner (new logic)")
        while True:
            choice = input("Enter 1 or 2: ").strip()
            if choice in {"1", "2"}:
                return int(choice)
            print("Invalid input. Please enter 1 or 2.")

    # Old cleaning method: removes intro paragraphs matching common keywords
    def old_clean_intro(self, soup: BeautifulSoup):
        intro_phrases = [
            "about", "ko-fi", "tips for lilies", "planting a lily field",
            "t/n", "support", "follow", "master list", "novels"
        ]
        for p in soup.find_all("p"):
            txt = p.get_text(strip=True).lower()
            if any(kw in txt for kw in intro_phrases):
                print(f"Removing intro paragraph: {txt[:50]!r}")
                p.decompose()
            else:
                break  # Stop at first paragraph that doesn't match

    # Old cleaning method: removes outro starting from first element with outro keywords
    def old_clean_outro(self, soup: BeautifulSoup):
        outro_keywords = [
            "translator’s note", "translator's note", "tl note", "tl;", "author’s note",
            "ramblings", "finally posting", "thank you for reading", "support me",
            "as for the reason", "next chapter", "previous chapter", "read on", "thoughts?",
            "follow me", "ko-fi", "patreon", "buy me a coffee", "share this", "thoughts on", "check out these other novels"
        ]
        elements = soup.find_all(["p", "div", "section", "h2", "h3", "h4", "h5", "h6"])
        for i, el in enumerate(elements):
            text = el.get_text(strip=True).lower()
            if any(keyword in text for keyword in outro_keywords):
                print(f"Removing outro starting at element #{i}: {text[:60]!r}")
                for bad_el in elements[i:]:
                    bad_el.decompose()
                break

    def is_intro_paragraph(self, text):
        # Checks if text matches intro regex patterns
        return any(pat.match(text) for pat in self.intro_patterns)

    def is_outro_paragraph(self, text):
        # Checks if text matches outro regex patterns
        return any(pat.match(text) for pat in self.outro_patterns)

    # New cleaner removes typical junk elements, scripts, styles, ads, and comments
    def new_remove_junk(self, soup: BeautifulSoup):
        for tag in soup(["script", "style", "footer", "nav", "aside", "form"]):
            tag.decompose()

        selectors = [
            "#jp-post-flair", ".sharedaddy", ".sd-sharing", ".jetpack-likes-widget-wrapper",
            "#jp-relatedposts", "#comments", ".entry-footer", ".comment-area", "#comment-area",
            ".comments-title", ".comment-list", ".comment-content"
        ]
        for sel in selectors:
            for el in soup.select(sel):
                print(f"Removing junk element: {sel}")
                el.decompose()

        # Remove paragraphs containing junk text based on junk_patterns regex
        for p in soup.find_all("p"):
            if self.junk_patterns.search(p.get_text()):
                print(f"Removing junk paragraph: {p.get_text()[:50]!r}")
                p.decompose()

    # New cleaner removes intro paragraphs using regex patterns
    def new_clean_intro(self, soup: BeautifulSoup):
        for p in list(soup.find_all("p")):
            txt = p.get_text(strip=True)
            if self.is_intro_paragraph(txt):
                print(f"Removing intro paragraph: {txt[:50]!r}")
                p.decompose()
            else:
                break

    # New cleaner removes outro paragraphs and related elements, including Ko-fi images and links
    def new_clean_outro(self, soup: BeautifulSoup):
        body = soup.body or soup
        all_elements = list(body.descendants)

        found = None
        for el in all_elements:
            if not hasattr(el, 'get_text'):
                continue
            text = el.get_text(strip=True)
            if self.is_outro_paragraph(text):
                found = el
                break

        if found:
            current = found
            while current and not hasattr(current, 'decompose'):
                current = current.parent

            if current and current.parent:
                siblings = list(current.parent.contents)
                start = False
                for sibling in siblings:
                    if sibling == current:
                        start = True
                    if start:
                        try:
                            sibling.decompose()
                        except Exception:
                            pass

        # Remove Ko-fi and similar donation images
        for img in soup.find_all("img"):
            alt = img.get("alt", "").lower()
            title = img.get("title", "").lower()
            src = img.get("src", "").lower()
            if any(x in alt or x in title or x in src for x in ["ko-fi", "kofi", "patreon", "buymeacoffee"]):
                print(f"Removing Ko-fi image")
                img.decompose()

        # Remove Ko-fi and donation links
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(x in href for x in ["ko-fi", "kofi", "patreon", "buymeacoffee"]):
                print(f"Removing Ko-fi link")
                a.decompose()

    # Attempt to identify main content of chapter by common container classes or fallback to largest div
    def extract_main_content(self, soup: BeautifulSoup):
        content_div = soup.select_one(".entry-content")
        if content_div and len(content_div.get_text(strip=True)) > 30 and content_div.find_all("p"):
            print(f"Using .entry-content with length: {len(content_div.get_text(strip=True))}")
            return content_div

        candidates = soup.select(".post-content, article, #content, .content, .main-content, entry-content")
        for c in candidates:
            if c.find_all("p") and len(c.get_text(strip=True)) > 30:
                return c

        divs = soup.find_all("div")
        if divs:
            largest = max(divs, key=lambda d: len(d.get_text(strip=True)))
            print(f"Fallback largest div length: {len(largest.get_text(strip=True))}")
            return largest

        return soup.body or soup

    # Wrap cleaned content in proper XHTML template with UTF-8 encoding and title
    def wrap_xhtml(self, content: str, title: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta charset="UTF-8"/>
    <title>{title}</title>
  </head>
  <body>
{content}
  </body>
</html>"""

    # Clean an individual HTML/XHTML file based on selected mode and return cleaned XHTML string
    def clean_html_file(self, src_path: Path, mode: int = 2) -> str:
        print(f"\n📂 Cleaning file: {src_path.name}")
        raw_html = src_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(raw_html, "html.parser")

        content_block = self.extract_main_content(soup)
        print(f"Raw length before cleaning: {len(content_block.get_text(strip=True))}")

        if mode == 1:
            # Use old cleaning logic
            self.old_clean_intro(content_block)
            self.old_clean_outro(content_block)
        else:
            # Use new cleaning logic
            self.new_remove_junk(content_block)
            self.new_clean_intro(content_block)
            self.new_clean_outro(content_block)

        text = content_block.get_text(strip=True)
        print(f"✅ Cleaned length: {len(text)}")

        if not text or len(text) < 30:
            print(f"⚠ Skipped: {src_path.name} (too short)")
            return ""

        # Extract chapter number from filename to label chapter heading
        chapter_num = re.search(r"(\d+)", src_path.name)
        chapter_label = chapter_num.group(1).lstrip("0") if chapter_num else "?"

        heading = f"<h1>Chapter {chapter_label}</h1>\n"
        cleaned_content = heading + str(content_block)
        return self.wrap_xhtml(cleaned_content, f"Chapter {chapter_label}")

    # Clean all HTML/XHTML files in input folder and save cleaned files to output folder
    def clean_all_html(self, mode: int = 2):
        print("🧹 Cleaning all files …")
        files = sorted(list(self.input_folder.glob("*.html")) + list(self.input_folder.glob("ch*.xhtml")))
        for file in files:
            cleaned = self.clean_html_file(file, mode)
            if cleaned:
                out_path = self.output_folder / file.name.replace(".html", ".xhtml")
                out_path.write_text(cleaned, encoding="utf-8")
                print(f"✔ Saved → {out_path.name}")
            else:
                print(f"⏭ Skipped: {file.name}")


if __name__ == "__main__":
    cleaner = ChapterCleaner()
    selected_mode = cleaner.select_mode()  # User selects cleaning mode interactively
    cleaner.clean_all_html(mode=selected_mode)
