import os
import sys
import base64
import pathlib
import zipfile
from ebooklib import epub, ITEM_DOCUMENT, ITEM_IMAGE
from bs4 import BeautifulSoup
from weasyprint import HTML

class EPUBToPDF:
    # ============================
    # Default CSS Styling (no watermark)
    # ============================
    CUSTOM_CSS = """
    <style>
    @page {
        margin: 2.5cm 2cm 2cm 2cm;
        @bottom-center {
            content: "Page " counter(page);
            font-size: 10pt;
            color: #888;
        }
    }
    body {
        font-family: "Times New Roman", serif;
        font-size: 12pt;
        line-height: 1.6;
        color: #222;
        background: #fcfcfc;
        margin: 0;
    }
    h1, h2, h3 {
        page-break-before: always;
        font-weight: bold;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #333;
        margin-top: 3em;
        margin-bottom: 1.5em;
        border-bottom: 2px solid #ddd;
        padding-bottom: 0.3em;
    }
    p {
        text-align: justify;
        margin: 1em 0;
    }
    img {
        max-width: 95%;
        height: auto;
        display: block;
        margin: 1em auto;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    div.chapter {
        break-inside: avoid;
    }
    img, p {
        break-inside: avoid;
    }
    </style>
    """

    # ============================
    # Full-page image styling (cover & illustrations)
    # ============================
    FULLPAGE_CSS = """
    <style>
    @page fullpage {
        size: A4;
        margin: 0;
    }
    .full-page, .cover-page {
        page: fullpage;
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        margin: 0;
        padding: 0;
    }
    .full-page img, .cover-page img {
        position: absolute;
        top: 0; left: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    </style>
    """

    def encode_image_item(self, item):
        mime = item.media_type
        data = item.get_content()
        b64 = base64.b64encode(data).decode('utf-8')
        return f"data:{mime};base64,{b64}"

    def encode_image_data(self, mime, data):
        b64 = base64.b64encode(data).decode('utf-8')
        return f"data:{mime};base64,{b64}"

    def find_cover_image(self, book, epub_path):
        cover_id_entry = book.get_metadata('OPF', 'cover')
        cover_id = cover_id_entry[0][0] if cover_id_entry else None

        if cover_id:
            for item in book.get_items_of_type(ITEM_IMAGE):
                if (item.id and item.id == cover_id) or (item.file_name and cover_id in item.file_name):
                    return self.encode_image_item(item)

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
                        for image in book.get_items_of_type(ITEM_IMAGE):
                            if image.file_name and pathlib.PurePosixPath(image.file_name).name.lower() == filename:
                                return self.encode_image_item(image)
                        try:
                            with zipfile.ZipFile(epub_path, 'r') as zf:
                                for entry in zf.infolist():
                                    if pathlib.PurePosixPath(entry.filename).name.lower() == filename:
                                        raw_data = zf.read(entry.filename)
                                        mime = 'image/jpeg' if filename.endswith(('.jpg', '.jpeg')) else 'image/png'
                                        return self.encode_image_data(mime, raw_data)
                        except Exception:
                            pass
        images = list(book.get_items_of_type(ITEM_IMAGE))
        if images:
            return self.encode_image_item(images[0])
        return None

    def convert_html_with_embedded_images(self, book, fullpage_images=False):
        image_map = {
            item.file_name.replace('\\', '/'): self.encode_image_item(item)
            for item in book.get_items_of_type(ITEM_IMAGE)
        }

        html_chapters = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), 'html.parser')

            # Inline all images
            for img in soup.find_all('img'):
                src = img.get('src')
                if src:
                    filename = os.path.basename(src.strip().replace('\\', '/'))
                    for key in image_map:
                        if key.endswith(filename):
                            img['src'] = image_map[key]
                            break

            # Detect if the chapter is mostly just one image
            only_image = (
                fullpage_images and
                len(soup.find_all()) == 1 and
                soup.find('img')
            )

            content_html = str(soup)
            if only_image:
                # Wrap in full-page container
                content_html = f'<div class="full-page">{content_html}</div>'
            else:
                content_html = f'<div class="chapter">{content_html}</div>'

            html_chapters.append(content_html)

        return html_chapters

    def epub_to_pdf_with_cover(self, epub_path, output_pdf, fullpage_images=False):
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
        content = self.convert_html_with_embedded_images(book, fullpage_images)

        css = self.CUSTOM_CSS + (self.FULLPAGE_CSS if fullpage_images else "")
        full_html = f"<html><head><meta charset='utf-8'>{css}</head><body>{cover_html}{''.join(content)}</body></html>"

        print("Writing PDF...")
        HTML(string=full_html).write_pdf(output_pdf)
        print(f"✅ Done! PDF saved to: {output_pdf}")

    def convert_all_in_folder(self, folder_path, fullpage_images=False):
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
                self.epub_to_pdf_with_cover(str(epub_file), str(output_pdf), fullpage_images)
            except Exception as e:
                print(f"Failed to convert {epub_file.name}: {e}")

        print("\nAll conversions done.")

    def run(self):
        self.suppress_glib_warnings()
        try:
            choice = input("Convert (1) single EPUB or (2) all EPUBs in folder? Enter 1 or 2: ").strip()
            fullpage_choice = input("Do you want images (like cover and illustrations) to fill the entire page? (y/n): ").strip().lower() == 'y'

            if choice == "1":
                epub_path = input("Enter path to EPUB: ").strip('"')
                base_name = pathlib.Path(epub_path).stem
                downloads_dir = str(pathlib.Path.home() / "Downloads")
                output_pdf = os.path.join(downloads_dir, base_name + ".pdf")
                self.epub_to_pdf_with_cover(epub_path, output_pdf, fullpage_choice)
            elif choice == "2":
                folder_path = input("Enter folder path containing EPUBs: ").strip('"')
                self.convert_all_in_folder(folder_path, fullpage_choice)
            else:
                print("Invalid option.")
        finally:
            self.restore_stderr()

    def suppress_glib_warnings(self):
        os.environ["G_MESSAGES_DEBUG"] = ""
        os.environ["G_DEBUG"] = ""
        try:
            import logging
            logging.getLogger("gi.repository.GLib").setLevel(logging.CRITICAL)
        except Exception:
            pass
        sys.stderr = open(os.devnull, 'w')

    def restore_stderr(self):
        sys.stderr = sys.__stderr__
