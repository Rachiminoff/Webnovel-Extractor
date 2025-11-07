import os
import subprocess
import requests
from pathlib import Path
from bs4 import BeautifulSoup

# Optional import for EbookLib EPUB creation
try:
    from ebooklib import epub
except ImportError:
    epub = None

class EpubCompiler:
    def __init__(self):
        # Define directory for markdown/xhtml files (fan translations)
        self.downloads_path = Path.home() / "Downloads"
        self.markdown_dir = self.downloads_path / "fan_tl_markdown"
        # If fan_tl_markdown doesn't exist, fallback to fan_tl_chapters
        if not self.markdown_dir.exists():
            self.markdown_dir = self.downloads_path / "fan_tl_chapters"

        # Directory for images used inside chapters
        self.images_dir = self.markdown_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def check_pandoc(self):
        # Check if pandoc is installed by running "pandoc --version"
        try:
            subprocess.run(["pandoc", "--version"], check=True, stdout=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            print("❌ Pandoc not found. Install from https://pandoc.org")
            return False

    def check_ebook_convert(self):
        # Check if Calibre's ebook-convert tool is installed
        try:
            subprocess.run(["ebook-convert", "--version"], check=True, stdout=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            print("❌ Calibre's ebook-convert not found. Install from https://calibre-ebook.com/")
            return False

    def get_xhtml_files(self):
        # List all .xhtml files in the markdown directory, sorted by filename
        return sorted(
            (self.markdown_dir / f for f in os.listdir(self.markdown_dir) if f.endswith('.xhtml')),
            key=lambda f: f.name
        )

    def download_image(self, url):
        """
        Download an image from a URL and save it in the images directory.
        If image already exists, skip downloading.
        """
        print(f"⬇️ Downloading image from URL: {url}")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            print(f"❌ Failed to download image: {e}")
            return None
        
        # Determine filename from URL and ensure proper extension
        filename = url.split("/")[-1].split("?")[0]
        if not filename:
            filename = "image.jpg"
        elif not any(filename.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif"]):
            filename += ".jpg"

        image_path = self.images_dir / filename
        # Skip download if already exists
        if image_path.exists():
            print(f"ℹ️ Image already downloaded: {filename}")
            return image_path

        # Write image content to file
        with open(image_path, "wb") as f:
            f.write(response.content)
        return image_path

    def fix_images_in_xhtml(self, xhtml_path):
        """
        Parse an XHTML file and replace external image URLs with local paths
        after downloading images locally.
        """
        print(f"🔍 Processing images in {xhtml_path.name}")
        with open(xhtml_path, encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        changed = False
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('http'):
                local_path = self.download_image(src)
                if local_path:
                    # Change image src to local relative path for EPUB
                    img['src'] = f"images/{local_path.name}"
                    changed = True

        # Overwrite XHTML file if changes were made
        if changed:
            with open(xhtml_path, "w", encoding='utf-8') as f:
                f.write(str(soup))

    def get_metadata(self):
        """
        Prompt user to enter book metadata: title, author, language,
        output filename, and optional cover image URL.
        Downloads cover image if URL is provided.
        """
        print("\n📖 Enter book metadata:")
        title = input("Title: ").strip()
        author = input("Author: ").strip()
        language = input("Language (e.g., en, zh): ").strip()
        file_name = input("Output EPUB name (no extension): ").strip()
        cover_url = input("Cover image URL (optional, leave blank if none): ").strip()
        
        cover_path = None
        if cover_url:
            cover_path = self.download_image(cover_url)
            if cover_path is None:
                print("⚠️ Proceeding without a cover image.")
        
        return {
            "title": title,
            "author": author,
            "language": language,
            "file_name": file_name,
            "cover": cover_path
        }

    def write_metadata(self, metadata):
        """
        Write basic metadata in YAML format for Pandoc usage.
        """
        meta_path = self.markdown_dir / "metadata.yaml"
        meta_lines = [
            f'title: "{metadata["title"]}"',
            f'author: "{metadata["author"]}"',
            f'language: "{metadata["language"]}"'
        ]
        meta_path.write_text("\n".join(meta_lines) + "\n", encoding="utf-8")
        return meta_path

    def compile_epub_pandoc(self, files, metadata_path, output_path, cover_path=None):
        """
        Use Pandoc to compile EPUB from XHTML files, applying metadata and optional cover.
        """
        cmd = [
            "pandoc",
            *[str(f) for f in files],
            "--metadata-file", str(metadata_path.name),
            "--toc",
            "--toc-depth=1",
            "-o", str(output_path.name)
        ]
        if cover_path:
            cmd += ["--epub-cover-image", str(cover_path.resolve())]

        print("\n📘 Creating EPUB with Pandoc…")
        try:
            subprocess.run(cmd, cwd=self.markdown_dir, check=True)
            print(f"✅ EPUB saved to: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during EPUB creation:\n{e}")

    def compile_epub_ebook_convert(self, files, metadata, output_path, cover_path=None):
        """
        Use Calibre's ebook-convert to generate EPUB.
        Combines all XHTML files into one HTML file first.
        """
        combined_html_path = self.markdown_dir / "combined_for_ebook_convert.html"
        print("\n📝 Combining XHTML files for ebook-convert…")
        combined_content = ""
        for f in files:
            content = f.read_text(encoding="utf-8")
            combined_content += f"\n<!-- {f.name} -->\n" + content
        combined_html_path.write_text(combined_content, encoding="utf-8")

        cmd = [
            "ebook-convert",
            str(combined_html_path),
            str(output_path)
        ]
        if cover_path:
            cmd += ["--cover", str(cover_path.resolve())]
        if metadata.get("title"):
            cmd += ["--title", metadata["title"]]
        if metadata.get("author"):
            cmd += ["--authors", metadata["author"]]
        if metadata.get("language"):
            cmd += ["--language", metadata["language"]]

        print("\n📗 Creating EPUB with Calibre's ebook-convert…")
        try:
            subprocess.run(cmd, check=True)
            print(f"✅ EPUB saved to: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error during EPUB creation:\n{e}")
        finally:
            # Clean up temporary combined HTML
            combined_html_path.unlink(missing_ok=True)

    def compile_epub_ebooklib(self, files, metadata, output_path, cover_path=None):
        """
        Use Python's EbookLib library to generate EPUB file.
        """
        if epub is None:
            print("❌ ebooklib library not installed. Install with: pip install ebooklib")
            return

        print("\n📙 Creating EPUB with EbookLib…")
        book = epub.EpubBook()

        # Set metadata fields with fallbacks
        book.set_title(metadata["title"] or "Untitled")
        book.set_language(metadata["language"] or "en")
        book.add_author(metadata["author"] or "Unknown")

        # Set cover image if available
        if cover_path and cover_path.exists():
            book.set_cover(cover_path.name, cover_path.read_bytes())

        # Add each XHTML file as a chapter
        chapters = []
        for f in files:
            content = f.read_text(encoding="utf-8")
            chap = epub.EpubHtml(title=f.stem, file_name=f.name, content=content)
            book.add_item(chap)
            chapters.append(chap)

        # Define table of contents and spine order
        book.toc = tuple(chapters)
        book.spine = ['nav'] + chapters
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        epub.write_epub(str(output_path), book)
        print(f"✅ EPUB saved to: {output_path}")

    def run(self):
        """
        Main interactive method for user to choose EPUB creation method,
        then process files, fix images, collect metadata, and compile EPUB.
        """
        print("Choose EPUB compilation method:")
        print("1. Pandoc")
        print("2. Calibre's ebook-convert")
        print("3. EbookLib (Python library)")
        print("4. Exit")

        choice = input("> ").strip()
        if choice not in {"1", "2", "3"}:
            print("Exiting.")
            return

        # Check for required tools based on choice
        if choice == "1" and not self.check_pandoc():
            return
        if choice == "2" and not self.check_ebook_convert():
            return
        if choice == "3" and epub is None:
            print("❌ EbookLib not installed. Run: pip install ebooklib")
            return

        files = self.get_xhtml_files()
        if not files:
            print("❌ No XHTML files found.")
            return

        # Fix external image URLs to local files for EPUB compatibility
        for f in files:
            self.fix_images_in_xhtml(f)

        # Collect metadata info interactively
        metadata = self.get_metadata()
        output_path = self.downloads_path / f"{metadata['file_name']}.epub"

        # For Pandoc, write YAML metadata file
        meta_path = self.write_metadata(metadata)

        # Call appropriate compilation method
        if choice == "1":
            self.compile_epub_pandoc(files, meta_path, output_path, metadata["cover"])
            # Remove temporary metadata file
            meta_path.unlink(missing_ok=True)
        elif choice == "2":
            self.compile_epub_ebook_convert(files, metadata, output_path, metadata["cover"])
        elif choice == "3":
            self.compile_epub_ebooklib(files, metadata, output_path, metadata["cover"])


if __name__ == "__main__":
    compiler = EpubCompiler()
    compiler.run()
