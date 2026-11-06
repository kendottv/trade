#!/usr/bin/env python3
"""離線截圖證據（AC-11）。"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "heatmap_evidence"
OUT.mkdir(exist_ok=True)
HTML = ROOT / "web" / "heatmap_fixtures.html"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(HTML.as_uri())

        # 紙上 × 今日漲跌熱力圖
        page.evaluate("loadScene('paper_normal')")
        page.evaluate("setColorMode('paper','day')")
        page.evaluate("setViewMode('paper','heat')")
        page.wait_for_selector("#paper-heatmap .hm-cell", timeout=5000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "paper_day_heat.png"), full_page=True)

        # 紙上 × 買入後損益熱力圖
        page.evaluate("setColorMode('paper','pnl')")
        page.wait_for_selector("#paper-heatmap .hm-cell", timeout=5000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "paper_pnl_heat.png"), full_page=True)

        # 紙上 × 表格視圖
        page.evaluate("setViewMode('paper','table')")
        page.wait_for_selector("#pos tr:nth-child(2)", timeout=5000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "paper_table.png"), full_page=True)

        # 模擬 × 正常（非過期）熱力圖
        page.evaluate("loadScene('sim_normal')")
        page.evaluate("setColorMode('sim','day')")
        page.evaluate("setViewMode('sim','heat')")
        page.wait_for_selector("#sim-heatmap .hm-cell", timeout=5000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "sim_normal_day_heat.png"), full_page=True)

        # 模擬 × 買入後損益熱力圖
        page.evaluate("setColorMode('sim','pnl')")
        page.wait_for_selector("#sim-heatmap .hm-cell", timeout=5000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "sim_normal_pnl_heat.png"), full_page=True)

        # paper_missing：切回熱力圖，確認無法配置面積清單
        page.evaluate("loadScene('paper_missing')")
        page.evaluate("setViewMode('paper','heat')")
        page.evaluate("setColorMode('paper','day')")
        page.wait_for_selector("#paper-unalloc", state="visible", timeout=5000)
        page.wait_for_function(
            "document.getElementById('paper-unalloc').textContent.includes('無法配置面積')",
            timeout=5000
        )
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "paper_missing.png"), full_page=True)

        # paper_empty：熱力圖空態
        page.evaluate("loadScene('paper_empty')")
        page.evaluate("setViewMode('paper','heat')")
        page.wait_for_selector("#paper-heatmap .empty", timeout=5000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "paper_empty.png"), full_page=True)

        # paper_invalid_cost：熱力圖 + pnl 模式，磚上「—」
        page.evaluate("loadScene('paper_invalid_cost')")
        page.evaluate("setViewMode('paper','heat')")
        page.evaluate("setColorMode('paper','pnl')")
        page.wait_for_selector("#paper-heatmap .hm-cell", timeout=5000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "paper_invalid_cost.png"), full_page=True)

        # sim_stale
        page.evaluate("loadScene('sim_stale')")
        page.evaluate("setViewMode('sim','heat')")
        page.wait_for_selector("#sim-heatmap .hm-cell", timeout=5000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "sim_stale.png"), full_page=True)

        # load_fail：切回熱力圖空態
        page.evaluate("loadScene('load_fail')")
        page.evaluate("setViewMode('paper','heat')")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "load_fail.png"), full_page=True)

        browser.close()
    print(f"截圖已輸出至 {OUT}")

if __name__ == "__main__":
    main()
