#!/usr/bin/env python3
"""離線 DOM 面積量測（AC-3）。需 Playwright + Chromium。"""
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("請先安裝：pip install playwright && playwright install chromium")
    sys.exit(2)

ROOT = Path(__file__).resolve().parent
HTML = ROOT / "web" / "heatmap_fixtures.html"

# 與 fixture 中 paper_normal 的市值一致
EXPECTED = {
    "2330": 52000 / 132600,
    "2317": 21000 / 132600,
    "2454": 41000 / 132600,
    "2881": 18600 / 132600,
}

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(HTML.as_uri())
        page.evaluate("loadScene('paper_normal')")
        page.wait_for_selector(".hm-cell", timeout=8000)
        tiles = page.query_selector_all(".hm-cell")
        if not tiles:
            print("FAIL: no .hm-cell found")
            sys.exit(1)
        areas = {}
        total = 0.0
        for t in tiles:
            code = t.get_attribute("data-code")
            box = t.bounding_box()
            if box and code:
                a = box["width"] * box["height"]
                areas[code] = a
                total += a
        if total <= 0:
            print("FAIL: zero total area")
            sys.exit(1)
        max_dev = 0.0
        fails = []
        for code, exp in EXPECTED.items():
            if code not in areas:
                fails.append(f"{code} missing from DOM")
                continue
            got = areas[code] / total
            dev = abs(got - exp)
            max_dev = max(max_dev, dev)
            if dev > 0.01:
                fails.append(f"{code}: got={got:.4f} exp={exp:.4f} dev={dev:.4f}")
        browser.close()
        if fails:
            print("FAIL max_dev=%.4f" % max_dev)
            for f in fails:
                print(" ", f)
            sys.exit(1)
        print("AREA CHECK PASS max_dev=%.4f" % max_dev)
        sys.exit(0)

if __name__ == "__main__":
    main()
