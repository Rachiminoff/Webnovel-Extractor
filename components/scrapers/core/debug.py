from pathlib import Path

def save_debug(page, output_dir, name):
    debug_dir = Path(output_dir) / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    safe = ''.join(c if c.isalnum() or c in '._-' else '_' for c in name)
    try:
        (debug_dir / f"{safe}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass
    try:
        page.screenshot(path=str(debug_dir / f"{safe}.png"), full_page=True)
    except Exception:
        pass
