"""Capture and compare Cleo CV screenshots from the real example server.

Run ``just serve-example`` first, then:

    uv run python e2e_tests/cleo_json_resume_roundtrip.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8000"
VIEWPORT = {"width": 1280, "height": 1600}
OUTPUT_DIR = Path("/tmp/django-resume-cleo-roundtrip")


def cached_chromium() -> str | None:
    cache_dir = Path.home() / "Library" / "Caches" / "ms-playwright"
    matches = sorted(
        cache_dir.glob("chromium_headless_shell-*/**/chrome-headless-shell")
    )
    return str(matches[-1]) if matches else None


def capture(slug: str) -> bytes:
    with sync_playwright() as playwright:
        executable_path = cached_chromium()
        browser = playwright.chromium.launch(executable_path=executable_path)
        page = browser.new_page(viewport=VIEWPORT)
        page.emulate_media(media="screen")
        page.goto(f"{BASE_URL}/resume/{slug}/cv/", wait_until="networkidle")
        data = page.screenshot(full_page=True)
        browser.close()
        return data


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    before = capture("queen-cleo")
    after = capture("queen-cleo-roundtrip")
    before_path = OUTPUT_DIR / "queen-cleo.png"
    after_path = OUTPUT_DIR / "queen-cleo-roundtrip.png"
    before_path.write_bytes(before)
    after_path.write_bytes(after)
    if before != after:
        print(f"screenshot byte diff: {before_path} != {after_path}")
        return 1
    print(f"screenshot byte diff: 0 ({before_path} == {after_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
