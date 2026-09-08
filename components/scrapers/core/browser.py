from time import sleep

def stabilize_page(page, attempts=6, delay=0.6):
    """Wait until visible body text stops changing significantly."""
    previous = None
    for _ in range(attempts):
        try:
            current = len(page.locator("body").inner_text(timeout=3000))
        except Exception:
            current = -1
        if previous is not None and current == previous:
            return
        previous = current
        sleep(delay)
