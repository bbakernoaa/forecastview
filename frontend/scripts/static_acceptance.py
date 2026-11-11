#!/usr/bin/env python3
"""Run a nested-path, no-backend browser acceptance check for a static bundle.

Requires Python Playwright and a Chromium executable. The app is served below
/<bundle-directory-name>/ so absolute-root asset paths and API requests fail
the acceptance checks.
"""

from __future__ import annotations

import argparse
import json
import shutil
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


def selection_for(site: Path) -> dict[str, str]:
    catalog = json.loads((site / "data/catalog.json").read_text())
    product = catalog["products"][0]["product"]
    dates = json.loads((site / "data" / product / "dates.json").read_text())["dates"]
    date = dates[-1]
    runs = json.loads((site / "data" / product / date / "runs.json").read_text())["runs"]
    run = runs[-1]
    run_dir = site / "data" / product / date / run
    variables = json.loads((run_dir / "variables.json").read_text())["variables"]
    variable = variables[0]["name"]
    times = json.loads((run_dir / "times.json").read_text())["forecast_hours"]
    fhr = str(times[0]["fhr"])
    return {"product": product, "date": date, "run": run, "variable": variable, "fhr": fhr}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, type=Path, help="Generated static bundle directory")
    parser.add_argument("--screenshots", required=True, type=Path, help="Directory for acceptance PNGs")
    parser.add_argument("--port", type=int, default=8771)
    parser.add_argument("--chromium", default=shutil.which("chromium") or shutil.which("chromium-browser"))
    args = parser.parse_args()
    site = args.site.resolve()
    catalog = json.loads((site / "data/catalog.json").read_text())
    products = [item["product"] for item in catalog["products"]]
    if not args.chromium:
        parser.error("Chromium executable not found; set --chromium")
    if not (site / "index.html").is_file():
        parser.error(f"static site has no index.html: {site}")
    args.screenshots.mkdir(parents=True, exist_ok=True)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

    class QuietServer(ThreadingHTTPServer):
        def handle_error(self, request, client_address) -> None:
            # Browser teardown can close an in-flight static response; this
            # is expected during viewport changes and product switching.
            return

    server = QuietServer(
        ("127.0.0.1", args.port),
        lambda *handler_args: QuietHandler(*handler_args, directory=str(site.parent)),
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    prefix = f"/{site.name}/"
    base_url = f"http://127.0.0.1:{args.port}{prefix}"
    query = urlencode(selection_for(site))
    urls: list[str] = []
    external: list[str] = []
    api: list[str] = []
    errors: list[str] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=args.chromium,
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            viewports = [
                ("desktop-1440x900", {"width": 1440, "height": 900}),
                ("desktop-1024x768", {"width": 1024, "height": 768}),
                ("mobile-390x844", {"width": 390, "height": 844}),
            ]
            for name, viewport in viewports:
                page = browser.new_page(viewport=viewport)
                page.on("request", lambda request: urls.append(request.url))
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "console",
                    lambda message: errors.append(message.text) if message.type == "error" else None,
                )

                def guard(route):
                    url = route.request.url
                    if "/api/" in url:
                        api.append(url)
                        route.abort()
                    elif not url.startswith(f"http://127.0.0.1:{args.port}{prefix}"):
                        external.append(url)
                        route.abort()
                    else:
                        route.continue_()

                page.route("**/*", guard)
                response = page.goto(base_url + "?" + query, wait_until="domcontentloaded", timeout=20000)
                if response is None or response.status != 200:
                    raise RuntimeError(f"{name}: static entry document failed to load")
                if name == "mobile-390x844":
                    page.get_by_role("button", name="Map & Data Controls").click()

                product = page.get_by_label("Select forecast product")
                product.wait_for(state="visible", timeout=15000)
                page.wait_for_function(
                    "document.querySelector('[aria-label=\\\"Select forecast product\\\"]')?.value === "
                    + json.dumps(selection_for(site)["product"]),
                    timeout=10000,
                )
                page.wait_for_selector(".maplibregl-canvas", timeout=15000)
                page.wait_for_timeout(1200)

                if name == "desktop-1024x768" and len(products) > 1:
                    current_product = selection_for(site)["product"]
                    second_product = next(item for item in products if item != current_product)
                    second_dates = json.loads(
                        (site / "data" / second_product / "dates.json").read_text()
                    )["dates"]
                    request_start = len(urls)
                    product.select_option(value=second_product)
                    page.wait_for_function(
                        "document.querySelector('[aria-label=\\\"Select forecast product\\\"]')?.value === "
                        + json.dumps(second_product),
                        timeout=10000,
                    )
                    page.wait_for_timeout(800)
                    if not any(
                        f"/data/{second_product}/dates.json" in url
                        for url in urls[request_start:]
                    ):
                        raise AssertionError(f"switching to {second_product} did not load its dates")
                    date_selector = page.get_by_label("Select forecast date")
                    if date_selector.input_value() not in second_dates:
                        raise AssertionError(f"stale date remained after switching to {second_product}")
                    product.select_option(value=current_product)
                    page.wait_for_function(
                        "document.querySelector('[aria-label=\\\"Select forecast product\\\"]')?.value === "
                        + json.dumps(current_product),
                        timeout=10000,
                    )

                if name == "desktop-1440x900":
                    selected = selection_for(site)
                    frame = (
                        site / "data" / selected["product"] / selected["date"] / selected["run"]
                        / "field" / selected["variable"] / f"f{int(selected['fhr']):03d}.bin"
                    )
                    grid = frame.parents[2] / "grid.json"
                    if frame.is_file() and grid.is_file():
                        canvas = page.locator(".maplibregl-canvas")
                        box = canvas.bounding_box()
                        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        page.get_by_text("Value", exact=True).wait_for(state="visible", timeout=10000)
                        page.screenshot(path=str(args.screenshots / f"{name}.png"), full_page=True)
                        page.get_by_title("Collapse inspector panel").click()
                        page.get_by_title("Expand inspector panel").click()
                        assert product.input_value() == selected["product"]

                if name != "desktop-1440x900":
                    page.screenshot(path=str(args.screenshots / f"{name}.png"), full_page=True)
                print(f"{name}: loaded {product.input_value()}")
                page.close()
            browser.close()
    finally:
        server.shutdown()

    print(f"same-origin requests: {len(urls)}")
    print(f"external requests: {external}")
    print(f"API requests: {api}")
    print(f"browser errors: {errors}")
    if external or api or errors:
        raise SystemExit("static browser acceptance failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
