import re
from pathlib import Path
from bs4 import BeautifulSoup


class ChapterCleaner:

    intro_patterns = [
        re.compile(
            r'^\s*(about|ko-fi|tips for lilies|planting a lily field|'
            r'support|follow|master list|important update|'
            r'announcement|notice|password locked)',
            re.I
        ),
    ]

    outro_patterns = [
        re.compile(
            r'(author.?note|ramblings|thank you for reading|'
            r'next chapter|previous chapter|read on|'
            r'patreon|ko-fi|buy me a coffee|discord)',
            re.I
        ),
    ]

    junk_patterns = re.compile(
        r"(table of contents|toc|back to top|comment|reblog|ko-fi|patreon|"
        r"insidethemirror|wordpress\.com|please read at|novelupdates|click here|read more|"
        r"continue reading|subscribe|newsletter|join.*discord)",
        re.I
    )

    SOCIAL_REGEX = re.compile(
        r"(discord|twitter|facebook|instagram|telegram|reddit|patreon|ko-?fi)",
        re.I
    )

    SUPPORT_REGEX = re.compile(
        r"(support.*translator|support.*team|donate|commission|early access|advance chapter|sponsor)",
        re.I
    )

    WATERMARK_REGEX = re.compile(
        r"(read.*?(?:at|on)\s+\w+|stolen from|support the translator|please visit|original source)",
        re.I
    )

    NOTICE_REGEX = re.compile(
        r"(important update|important notice|announcement|site notice|password locked|"
        r"join my discord.*password|discord.*password|jjwxc|novelupdates|"
        r"grammar mistakes|sorry for any grammar mistakes|release schedule|"
        r"translation update|please join my discord|terribly sorry for the inconvenience)",
        re.I
    )

    DISCLAIMER_PHRASES = [
        "fan translation presented by",
        "this novel does not belong to me",
        "does not belong to me",
        "not mine",
        "grammar mistakes",
        "important notice",
        "important update",
        "password locked",
        "jjwxc",
        "please join my discord",
        "terribly sorry for the inconvenience",
    ]

    def __init__(self, input_folder=None, output_folder=None):
        downloads_path = Path.home() / "Downloads"
        self.input_folder = input_folder or downloads_path / "fan_tl_chapters"
        self.output_folder = output_folder or downloads_path / "fan_tl_markdown"
        self.output_folder.mkdir(parents=True, exist_ok=True)

    # ---------------- MAIN ----------------

    def run(self, mode=2):
        self.clean_all_html(mode)

    def clean_all_html(self, mode=2):
        print("🧹 Cleaning all files …")

        files = sorted(
            list(self.input_folder.glob("*.html")) +
            list(self.input_folder.glob("*.xhtml")),
            key=lambda p: int(
                self.extract_chapter_number(p.name)
                if self.extract_chapter_number(p.name).isdigit()
                else 999999
            )
        )

        for file in files:
            cleaned = self.clean_html_file(file, mode)

            out_path = self.output_folder / file.with_suffix(".xhtml").name
            out_path.write_text(cleaned, encoding="utf-8")
            print(f"✔ Saved → {out_path.name}")

    # ---------------- CLEANING ----------------

    def clean_html_file(self, src_path: Path, mode: int = 2) -> str:
        print(f"\n📂 Cleaning file: {src_path.name}")

        raw_html = src_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw_html, "html.parser")

        content = self.extract_main_content(soup)

        print(f"Raw length: {len(content.get_text(strip=True))}")

        self.remove_unwanted_tags(content)
        self.clean_lumo_artifacts(content)
        self.remove_lumo_control_artifacts(content)
        self.remove_empty_artifact_wrappers(content)
        self.remove_wp_important_update(content)   # ⭐ FIX HERE
        self.clean_notice_blocks(content)
        self.remove_announcement_blocks(content)
        self.clean_intro(content)
        self.clean_outro(content)
        self.remove_junk_paragraphs(content)
        self.remove_duplicate_paragraphs(content)
        self.remove_existing_chapter_titles(content)
        self.strip_attributes(content)

        text = content.get_text("\n", strip=True)

        print(f"Cleaned length: {len(text)}")

        if len(text.split()) < 150:
            print(f"⚠ Warning: {src_path.name} is short ({len(text.split())} words)")

        chapter_num = self.extract_chapter_number(src_path.name)
        heading = f"<h1>Chapter {chapter_num}</h1>\n"

        return self.wrap_xhtml(heading + str(content), f"Chapter {chapter_num}")

    # ---------------- SITE-SPECIFIC CLEANING ----------------

    def clean_lumo_artifacts(self, soup):
        """Remove Lumo Stories reader artifacts without touching chapter prose."""
        watermark = re.compile(
            r"^\s*read\s+on\s+lumo\s+stories\.\s*"
            r"unauthorized\s+reproduction\s+prohibited\.\s*$",
            re.I,
        )
        svg_artifact = re.compile(
            r"^\s*svg\d+(?:\s*\(icon\))?\s*$", re.I
        )

        # Remove decorative SVG elements first. Their accessibility labels can
        # otherwise be serialized by BeautifulSoup as text such as ``svg0``.
        for tag in list(soup.find_all("svg")):
            tag.decompose()

        # Remove standalone watermark and SVG placeholder text. Only target
        # exact artifact lines so ordinary prose containing similar words stays.
        for tag in list(soup.find_all(["p", "div", "span", "figure"])):
            text = tag.get_text(" ", strip=True)
            if watermark.fullmatch(text) or svg_artifact.fullmatch(text):
                tag.decompose()

        # Some downloads flatten artifacts directly into text nodes rather than
        # wrapping them in a dedicated element. Clean those exact text nodes too.
        for node in list(soup.find_all(string=True)):
            text = str(node).strip()
            if watermark.fullmatch(text) or svg_artifact.fullmatch(text):
                node.extract()

    def remove_lumo_control_artifacts(self, soup):
        """Remove reader UI controls that can survive after SVG removal.

        Lumo's chapter DOM can contain tiny button/input/icon wrappers inside
        the same container as the prose. After SVGs are removed, some wrappers
        serialize as a visible ``0`` or as an empty control with a border.
        These elements are reader UI, not chapter content.
        """
        artifact_text = {"", "0", "svg0", "svg0 (icon)", "icon"}

        # Reader controls should never be part of the cleaned chapter body.
        for tag in list(soup.find_all(["button", "input", "select", "textarea", "svg", "use", "symbol"])):
            tag.decompose()

        # Remove short, non-prose wrappers that only contain a leftover icon
        # label or counter. Keep normal paragraphs untouched.
        for tag in list(soup.find_all(["span", "div", "label", "figure", "a", "li"])):
            text = tag.get_text(" ", strip=True)
            norm = re.sub(r"\s+", " ", text).strip().lower()

            if norm in artifact_text:
                tag.decompose()

        # Horizontal separators around icon controls are visual UI noise in
        # downloaded chapters and can remain after their neighbouring controls
        # are removed.
        for tag in list(soup.find_all("hr")):
            tag.decompose()

    def remove_empty_artifact_wrappers(self, soup):
        """Repeatedly prune empty wrappers left behind by artifact removal."""
        wrapper_names = {"div", "span", "section", "figure", "label", "p", "li"}

        # Work from the deepest nodes upward so nested empty wrappers collapse.
        for _ in range(3):
            removed = False
            for tag in list(reversed(soup.find_all(wrapper_names))):
                if tag.find(["img", "br", "audio", "video"]) is not None:
                    continue
                if not tag.get_text(" ", strip=True) and not tag.find(True):
                    tag.decompose()
                    removed = True
            if not removed:
                break

    # ---------------- SAFE IMPORTANT UPDATE REMOVER ----------------

    def remove_wp_important_update(self, soup):
        heading = soup.find(
            lambda t:
            t.name in ["h1", "h2", "h3"]
            and "important update" in t.get_text(" ", strip=True).lower()
        )

        if not heading:
            return

        # remove ONLY until hr separator (safe boundary)
        current = heading

        while current:
            nxt = current.find_next_sibling()

            current.decompose()

            if not nxt:
                break

            if getattr(nxt, "name", None) == "hr":
                nxt.decompose()
                break

            current = nxt

    # ---------------- CORE ----------------

    def extract_main_content(self, soup):
        candidates = soup.select(
            ".entry-content, .post-content, article, #content, .content, .main-content"
        )

        best, best_score = None, 0

        for c in candidates:
            score = self.content_score(c)
            if score > best_score:
                best, best_score = c, score

        return best or soup.body or soup

    def content_score(self, tag):
        text = tag.get_text(" ", strip=True)

        text_len = len(text)
        p_count = len(tag.find_all("p"))

        link_text = sum(len(a.get_text(" ", strip=True)) for a in tag.find_all("a"))

        density = text_len / max(link_text, 1)
        junk_hits = len(self.junk_patterns.findall(text))

        bonus = 200 if ('"' in text or "“" in text) else 0

        return text_len + (p_count * 50) + (density * 20) + bonus - (junk_hits * 200)

    # ---------------- TAG CLEANING ----------------

    def remove_unwanted_tags(self, soup):
        for tag in soup(["script", "style", "nav", "aside", "form", "iframe"]):
            tag.decompose()

    def clean_notice_blocks(self, soup):
        for tag in soup.find_all(["p"]):   # SAFE: only p
            text = tag.get_text(" ", strip=True).lower()

            if self.NOTICE_REGEX.search(text):
                tag.decompose()

    def remove_announcement_blocks(self, soup):
        for tag in soup.find_all(["p"]):   # SAFE: only p
            text = tag.get_text(" ", strip=True).lower()

            if self.NOTICE_REGEX.search(text):
                tag.decompose()

    def clean_intro(self, soup):
        blocks = soup.find_all(["p", "div", "section"])

        for el in blocks[:15]:
            txt = el.get_text(" ", strip=True)
            if any(p.search(txt) for p in self.intro_patterns):
                el.decompose()
            else:
                break

    def clean_outro(self, soup):
        blocks = soup.find_all(["p", "div", "section"])

        for i in range(len(blocks) - 1, -1, -1):
            txt = blocks[i].get_text(" ", strip=True)

            if any(p.search(txt) for p in self.outro_patterns):
                for el in blocks[i:]:
                    el.decompose()
                break

    def remove_junk_paragraphs(self, soup):
        for p in list(soup.find_all("p")):   # SAFE: only p

            text = p.get_text(" ", strip=True).lower()

            if (
                not text or
                self.NOTICE_REGEX.search(text) or
                self.junk_patterns.search(text) or
                self.SOCIAL_REGEX.search(text) or
                self.SUPPORT_REGEX.search(text) or
                self.WATERMARK_REGEX.search(text)
            ):
                p.decompose()

    def remove_duplicate_paragraphs(self, soup):
        seen = set()

        for tag in soup.find_all(["p"]):
            text = tag.get_text(" ", strip=True)
            norm = re.sub(r"\s+", " ", text.lower())

            if len(norm) < 15:
                continue

            if norm in seen:
                tag.decompose()
            else:
                seen.add(norm)

    def remove_existing_chapter_titles(self, soup):
        for h in soup.find_all(["h1", "h2"]):
            if re.search(r"(chapter|chap\.?)\s*\d+", h.get_text(), re.I):
                h.decompose()

    def strip_attributes(self, soup):
        for tag in soup.find_all(True):
            tag.attrs = {}

    # ---------------- UTIL ----------------

    def extract_chapter_number(self, name):
        m = re.search(r"chapter[_\-\s]*(\d+)", name, re.I)
        if m:
            return m.group(1)

        nums = re.findall(r"\d+", name)
        return nums[-1] if nums else "?"

    def wrap_xhtml(self, content, title):
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


if __name__ == "__main__":
    cleaner = ChapterCleaner()
    cleaner.run()