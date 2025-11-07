from components.downloader import ChapterDownloader
from components.Cleaner import ChapterCleaner
from components.compiler import EpubCompiler
from components.converter import EPUBToPDF
import time

class MainController:
    def __init__(self):
        self.downloader = ChapterDownloader()
        self.Cleaner = ChapterCleaner()
        self.compiler = EpubCompiler()
        self.converter = EPUBToPDF()

    def run(self):
        while True:
            print("\033[92m⚠️ Ignore any warnings--They are harmless and come from underlying libs.\n\033[0m") #green text
            time.sleep(3)
            print("\nWebnovel Extraction & Conversion Tool")
            print("========================================")
            print("1. Download chapters")
            print("2. Clean downloaded files")
            print("3. Compile into EPUB")
            print("4. Convert EPUB into PDF")
            print("5. Exit")
            print("========================================")
            choice = input("Choose an option (1–5): ").strip()

            if choice == "1":
                self.downloader.run()
            elif choice == "2":
                self.Cleaner.run()
            elif choice == "3":
                self.compiler.run()
            elif choice == "4":
                self.converter.run()
            elif choice == "5":
                print("Exiting. Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    controller = MainController()
    controller.run()
