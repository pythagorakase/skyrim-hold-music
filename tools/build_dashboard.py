#!/usr/bin/env python3
"""Build the portable listening dashboard from the repository's Markdown sources.

Run from any working directory. The main outputs are always
dashboard/palette-data.json and dashboard/index.html in this checkout.
Use --output to write the same standalone HTML to a second explicit destination,
for example an Obsidian vault. Nothing is hosted or uploaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from build_palette_data import (
    BuildError,
    DEFAULT_BANK,
    DEFAULT_DATE,
    DEFAULT_OUTPUT,
    DEFAULT_SPEC,
    REPO_ROOT,
    build_dataset,
    snapshot_date,
    write_dataset,
)

TEMPLATE = REPO_ROOT / "dashboard" / "index.template.html"
HTML_OUTPUT = REPO_ROOT / "dashboard" / "index.html"
DATA_TOKEN = "__PALETTE_DATA__"


def render_html(data, template):
    """Embed JSON safely inside the template's inline JavaScript."""
    if template.count(DATA_TOKEN) != 1:
        raise BuildError(f"Template must contain exactly one {DATA_TOKEN} token.")
    payload = (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    html = template.replace(DATA_TOKEN, payload)
    if "<!doctype html>" not in html.lower():
        raise BuildError("The dashboard template is missing its HTML doctype.")
    return html


def check_javascript(html, skip=False):
    """Use Node from PATH when available; it is not a build dependency."""
    if skip:
        return "JavaScript syntax check skipped (--skip-node-check)."
    node = shutil.which("node")
    if not node:
        return "Node not found on PATH; optional JavaScript syntax check skipped."
    scripts = re.findall(r"<script(?:\s[^>]*)?>([\s\S]*?)</script>", html, re.I)
    if not scripts:
        raise BuildError("No inline JavaScript was found in the dashboard.")
    with tempfile.TemporaryDirectory(prefix="hold-music-check-") as directory:
        check_path = Path(directory) / "dashboard.js"
        with check_path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(scripts))
        result = subprocess.run(
            [node, "--check", str(check_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode:
            details = result.stderr.strip() or result.stdout.strip()
            raise BuildError("JavaScript syntax check failed:\n" + details)
    return "JavaScript syntax check passed (Node from PATH)."


def write_html(html, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(html)


def parser():
    cli = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    cli.add_argument(
        "--output", type=Path,
        help="optional second HTML destination; the repository output is always built",
    )
    cli.add_argument(
        "--spec", type=Path, default=DEFAULT_SPEC,
        help="source spec (default: docs/bard-regional-music-spec.md)",
    )
    cli.add_argument(
        "--bank", type=Path, default=DEFAULT_BANK,
        help="idea bank (default: docs/bard-musical-traditions-exploration.md)",
    )
    cli.add_argument(
        "--date", type=snapshot_date, default=DEFAULT_DATE,
        help=f"editorial snapshot date, not build time (default: {DEFAULT_DATE})",
    )
    cli.add_argument(
        "--skip-node-check", action="store_true",
        help="skip the optional JavaScript syntax check even when Node is on PATH",
    )
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        if args.output:
            protected = {path.resolve() for path in (TEMPLATE, DEFAULT_OUTPUT, args.spec, args.bank)}
            if args.output.resolve() in protected:
                raise BuildError("The second HTML destination would overwrite a source or dataset file.")
        data, provenance = build_dataset(args.spec, args.bank, args.date)
        html = render_html(data, TEMPLATE.read_text(encoding="utf-8-sig"))
        check_message = check_javascript(html, args.skip_node_check)
        write_dataset(data)
        write_html(html, HTML_OUTPUT)
        outputs = [HTML_OUTPUT]
        if args.output and args.output.resolve() != HTML_OUTPUT.resolve():
            write_html(html, args.output)
            outputs.append(args.output)
    except (BuildError, OSError, KeyError, TypeError) as exc:
        cli.exit(1, f"Dashboard build failed: {exc}\n")
    print(check_message)
    print(json.dumps({
        "html": [str(path) for path in outputs],
        "dataset": str(DEFAULT_OUTPUT),
        "snapshot_date": data["updatedAt"],
        "bytes": len(html.encode("utf-8")),
        "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "counts": {key: len(data[key]) for key in ("finalists", "existing", "ideas", "boundaries")},
        **provenance,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
