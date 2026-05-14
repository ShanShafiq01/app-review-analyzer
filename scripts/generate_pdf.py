"""
PDF generator.

Converts the HTML reports to PDF using Playwright's headless Chromium print API.
Requires `playwright` to be installed (and `playwright install chromium` run once).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def html_to_pdf_async(html_path, pdf_path, format="A4"):
    """Convert one HTML file to PDF."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ImportError(
            "playwright required for PDF output. Install: pip install playwright && "
            "playwright install chromium"
        )

    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path).resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(f"file://{html_path}", wait_until="networkidle")
        await page.wait_for_timeout(2000)  # Let fonts settle
        # Disable sticky positioning for PDF — looks weird in print
        await page.add_style_tag(content="""
            .masthead, .sticky-nav { position: static !important; }
            .theme-meta { position: static !important; }
            .load-more, .controls { display: none !important; }
        """)
        await page.pdf(
            path=str(pdf_path),
            format=format,
            margin={"top": "0.5in", "bottom": "0.5in", "left": "0.4in", "right": "0.4in"},
            print_background=True,
        )
        await browser.close()
    return str(pdf_path)


def html_to_pdf(html_path, pdf_path, format="A4"):
    """Sync wrapper."""
    return asyncio.run(html_to_pdf_async(html_path, pdf_path, format))


def generate_pdf_reports(html_dir, pdf_dir=None):
    """Convert every HTML report in a directory to PDF."""
    html_dir = Path(html_dir)
    pdf_dir = Path(pdf_dir) if pdf_dir else html_dir
    pdf_dir.mkdir(parents=True, exist_ok=True)

    html_files = sorted(html_dir.glob("*.html"))
    pdf_files = []
    for html in html_files:
        pdf = pdf_dir / (html.stem + ".pdf")
        try:
            html_to_pdf(html, pdf)
            pdf_files.append(str(pdf))
        except Exception as exc:
            print(f"  PDF generation failed for {html.name}: {exc}", file=sys.stderr)
    return pdf_files


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--html-dir", required=True)
    parser.add_argument("--pdf-dir")
    args = parser.parse_args()
    for f in generate_pdf_reports(args.html_dir, args.pdf_dir):
        print(f)
