"""Command-line entry point for ``python -m banzena_inventory_check``."""

import argparse
import json

from .checker import check_inventory


def main(argv=None):
    """Parse CLI options, print a human or JSON report, and return its exit code."""
    parser = argparse.ArgumentParser(description="Check Banzena public shop inventory.")
    parser.add_argument("--base", required=True, help="Banzena public base URL")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    report = check_inventory(args.base)
    if args.as_json:
        # JSON output is intended for CI and other tools that consume evidence.
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        # The concise summary leaves details to each failed target below.
        print("%s: %s" % (report["status"].upper(), report.get("errors", [])))
        for item in report.get("hosts", []):
            _print_check(item["hostname"], item)
        for item in report.get("paths", []):
            _print_check(item["url"], item)
    # Raising SystemExit in the module guard makes this value visible to shells
    # and CI as 0 (pass), 1 (contract failure), or 2 (incomplete check).
    return report["exit_code"]


def _print_check(target, evidence):
    """Print one target and expand diagnostics only when action is needed."""
    status = evidence.get("status", "unknown")
    print("%s %s" % (target, status))
    if status in ("pass", "unknown"):
        return
    # Include source provenance and a short response sample so failures can be
    # understood without opening the full JSON evidence file.
    print("  advertised by: %s" % ", ".join(evidence.get("advertised_by", [])))
    print(
        "  HTTP %s; Content-Type: %s; fetched_at: %s"
        % (
            evidence.get("status_code", "unknown"),
            evidence.get("content_type", "unknown"),
            evidence.get("fetched_at", "unknown"),
        )
    )
    if "first_bytes" in evidence:
        print("  first bytes: %r" % evidence["first_bytes"])
    if evidence.get("error"):
        print("  error: %s" % evidence["error"])


if __name__ == "__main__":
    raise SystemExit(main())
