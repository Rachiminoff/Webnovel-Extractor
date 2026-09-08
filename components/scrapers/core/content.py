from bs4 import BeautifulSoup

def score_candidate(element):
    try:
        text = element.inner_text(timeout=3000).strip()
        if len(text) < 250:
            return -999
        paragraphs = element.locator("p").count()
        links = element.locator("a").count()
        score = min(len(text) / 500, 12) + min(paragraphs * 2, 20)
        if paragraphs and links / max(paragraphs, 1) < 0.7:
            score += 8
        tag = element.evaluate("el => el.tagName.toLowerCase()")
        if tag in {"article", "main"}:
            score += 5
        return score
    except Exception:
        return -999

def find_best_content(page, selectors):
    candidates = []
    seen = set()
    for selector in selectors:
        try:
            for element in page.locator(selector).all():
                key = element.evaluate("el => el.outerHTML.slice(0,120)")
                if key in seen:
                    continue
                seen.add(key)
                score = score_candidate(element)
                if score > -999:
                    candidates.append((score, element))
        except Exception:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]

def clean_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "iframe", "noscript"]):
        tag.decompose()
    return str(soup)
