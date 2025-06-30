from downloader import ChapterDownloader
from Cleaner import ChapterCleaner
from compiler import EpubCompiler

class MainController:
    def __init__(self):
        self.downloader = ChapterDownloader()
        self.cleaner = ChapterCleaner()
        self.compiler = EpubCompiler()

    def run(self):
        while True:
            print("\n Webnovel Extractor Tool")
            print("1. Download chapters")
            print("2. Clean downloaded files")
            print("3. Compile into EPUB")
            print("4. Exit")
            choice = input("Choose an option (1-4): ").strip()

            if choice == "1":
                self.downloader.run()
            elif choice == "2":
                self.cleaner.run()
            elif choice == "3":
                self.compiler.run()
            elif choice == "4":
                print("👋 Exiting.")
                break
            else:
                print("❌ Invalid choice. Try again.")


if __name__ == "__main__":
    controller = MainController()
    controller.run()
