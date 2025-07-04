import os
import sys
import base64
import pathlib
import zipfile
from ebooklib import epub, ITEM_DOCUMENT, ITEM_IMAGE
from bs4 import BeautifulSoup
from weasyprint import HTML

class EPUBToPDF:
    # Custom CSS for formatting the output PDF
    CUSTOM_CSS = """
    <style>
    @page {
        margin: 2cm 2.5cm 2cm 2.5cm;
        @bottom-center {
            content: "Page " counter(page);
            font-size: 10pt;
            color: gray;
        }
    }
    @page :first {
        margin: 0;
    }
    body {
        font-family: "Times New Roman", serif;
        font-size: 12pt;
        line-height: 1.5;
        color: #111;
        background: white;
        margin: 0;
    }
    h1, h2, h3 {
        page-break-before: always;
        font-weight: bold;
        color: #222;
        margin-top: 2em;
    }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1em auto;
    }
    .cover-page {
        page-break-after: always;
        width: 100vw;
        height: 100vh;
        overflow: hidden;
    }
    .cover-page img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        margin: 0;
        display: block;
    }
    div.chapter {
        break-inside: avoid;
    }
    img, p {
        break-inside: avoid;
    }
    </style>
    """

    # Converts a single EPUB image item into a base64-encoded data URI
    def encode_image_item(self, item):
        mime = item.media_type
        data = item.get_content()
        b64 = base64.b64encode(data).decode('utf-8')
        return f"data:{mime};base64,{b64}"

    # Converts raw image data into a base64-encoded data URI
    def encode_image_data(self, mime, data):
        b64 = base64.b64encode(data).decode('utf-8')
        return f"data:{mime};base64,{b64}"

    # Attempts to locate and extract the cover image from the EPUB
    def find_cover_image(self, book, epub_path):
        # Look for cover id in EPUB metadata
        cover_id_entry = book.get_metadata('OPF', 'cover')
        cover_id = cover_id_entry[0][0] if cover_id_entry else None
        print(f"[DEBUG] cover_id from metadata: {cover_id}")

        # First: Match by ID in image list
        if cover_id:
            for item in book.get_items_of_type(ITEM_IMAGE):
                if (item.id and item.id == cover_id) or (item.file_name and cover_id in item.file_name):
                    print(f"[DEBUG] Cover found via metadata: {item.file_name}")
                    return self.encode_image_item(item)

        # Second: Look for a file named "cover" in XHTML files
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            if item.file_name and 'cover' in item.file_name.lower():
                soup = BeautifulSoup(item.get_content(), 'lxml-xml')
                img_tag = soup.find('image') or soup.find('img')
                if img_tag:
                    href = (
                        img_tag.get('xlink:href') or
                        img_tag.get('{http://www.w3.org/1999/xlink}href') or
                        img_tag.get('href') or
                        img_tag.get('src')
                    )
                    if href:
                        filename = pathlib.PurePosixPath(href.strip()).name.lower()
                        print(f"[DEBUG] Looking for image file referenced in cover.xhtml: {filename}")
                        # Match filename against all EPUB image entries
                        for image in book.get_items_of_type(ITEM_IMAGE):
                            if image.file_name:
                                image_name = pathlib.PurePosixPath(image.file_name).name.lower()
                                if image_name == filename:
                                    print(f"[DEBUG] Cover found via cover.xhtml: {image.file_name}")
                                    return self.encode_image_item(image)
                        # If all else fails, check inside the ZIP structure manually
                        try:
                            with zipfile.ZipFile(epub_path, 'r') as zf:
                                for entry in zf.infolist():
                                    if pathlib.PurePosixPath(entry.filename).name.lower() == filename:
                                        print(f"[DEBUG] Cover found via ZIP fallback: {entry.filename}")
                                        raw_data = zf.read(entry.filename)
                                        mime = 'image/jpeg' if filename.endswith(('.jpg', '.jpeg')) else 'image/png'
                                        return self.encode_image_data(mime, raw_data)
                        except Exception as e:
                            print(f"[DEBUG] ZIP fallback failed: {e}")
                    else:
                        print("[DEBUG] No href/src found in cover.xhtml <image>/<img>")
                else:
                    print("[DEBUG] No <image> or <img> tag in cover.xhtml")

        # Final fallback: Use the first image in the EPUB
        images = list(book.get_items_of_type(ITEM_IMAGE))
        if images:
            print(f"[DEBUG] Fallback to first image: {images[0].file_name}")
            return self.encode_image_item(images[0])

        print("[DEBUG] No cover image found.")
        return None

    # Parses and inlines images inside HTML chapters
    def convert_html_with_embedded_images(self, book):
        image_map = {
            item.file_name.replace('\\', '/'): self.encode_image_item(item)
            for item in book.get_items_of_type(ITEM_IMAGE)
        }

        html_chapters = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), 'html.parser')

            # Inline <img src> using base64
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    filename = os.path.basename(src.strip().replace('\\', '/'))
                    for key in image_map:
                        if key.endswith(filename):
                            img['src'] = image_map[key]
                            break

            # Neutralize broken anchor links
            for a in soup.find_all('a', href=True):
                href = a['href']
                if '.xhtml' in href or '.html' in href:
                    a['href'] = '#' + href.split('#')[-1] if '#' in href else '#'

            html_chapters.append(f'<div class="chapter">{str(soup)}</div>')

        return html_chapters

    # Core logic to convert EPUB → PDF using extracted HTML and cover
    def epub_to_pdf_with_cover(self, epub_path, output_pdf):
        print("Reading EPUB...")
        book = epub.read_epub(epub_path)

        print("Extracting cover image...")
        cover_data_uri = self.find_cover_image(book, epub_path)
        cover_html = f'''
        <div class="cover-page">
            <img src="{cover_data_uri}" alt="Cover" />
        </div>
        ''' if cover_data_uri else ""

        print("Processing content...")
        content = self.convert_html_with_embedded_images(book)

        # Combine everything into final HTML
        full_html = f"<html><head><meta charset='utf-8'>{self.CUSTOM_CSS}</head><body>{cover_html}{''.join(content)}</body></html>"

        print("Writing PDF...")
        HTML(string=full_html).write_pdf(output_pdf)
        print(f"Done! PDF saved to: {output_pdf}")
    def convert_all_in_folder(self, folder_path):
            """
            Convert all .epub files in the given folder to PDFs,
            saving output PDFs in the same folder.
            """
            folder = pathlib.Path(folder_path)
            if not folder.is_dir():
                print(f"❌ Error: {folder_path} is not a valid directory.")
                return

            epub_files = list(folder.glob("*.epub"))
            if not epub_files:
                print("No EPUB files found in the specified folder.")
                return

            print(f"Found {len(epub_files)} EPUB(s). Starting conversion...")

            for epub_file in epub_files:
                output_pdf = epub_file.with_suffix(".pdf")
                print(f"\nConverting: {epub_file.name}")
                try:
                    self.epub_to_pdf_with_cover(str(epub_file), str(output_pdf))
                except Exception as e:
                    print(f"Failed to convert {epub_file.name}: {e}")

            print("\nAll conversions done.")

        # Entry point for standalone execution
    def run(self):
            self.suppress_glib_warnings()
            try:
                choice = input("Convert (1) single EPUB or (2) all EPUBs in folder? Enter 1 or 2: ").strip()
                if choice == "1":
                    epub_path = input("Enter path to EPUB: ").strip('"')
                    base_name = pathlib.Path(epub_path).stem
                    downloads_dir = str(pathlib.Path.home() / "Downloads")
                    output_pdf = os.path.join(downloads_dir, base_name + ".pdf")
                    self.epub_to_pdf_with_cover(epub_path, output_pdf)
                elif choice == "2":
                    folder_path = input("Enter folder path containing EPUBs: ").strip('"')
                    self.convert_all_in_folder(folder_path)
                else:
                    print("Invalid option.")
            finally:
                self.restore_stderr()

        # Suppress annoying GTK/GLib warnings from weasyprint/cairo (not very effective)
    def suppress_glib_warnings(self):
            os.environ["G_MESSAGES_DEBUG"] = ""
            os.environ["G_DEBUG"] = ""
            try:
                import logging
                logging.getLogger("gi.repository.GLib").setLevel(logging.CRITICAL)
            except Exception:
                pass
            sys.stderr = open(os.devnull, 'w')

    # Restore normal stderr
    def restore_stderr(self):
        sys.stderr = sys.__stderr__
