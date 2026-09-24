# Banzena public inventory checker

A small Python command-line tool that checks whether the public shop addresses advertised by Banzena resolve to the expected storefront responses. It is designed to give a customer and an engineer a reproducible, inspectable result—not merely a green check for a machine.

## Development philosophy

Code is written for people as well as computers. A future maintainer should be able to open the repository, understand what the checker promises, trace how it reaches a result, and safely change it without reverse-engineering hidden assumptions.

That principle guides the implementation:

- Names describe intent: `extract_inventory`, `inspect_host_response`, and `fetch_url` each have a clear responsibility.
- Functions stay focused. Parsing advertised addresses, validating responses, fetching URLs, building evidence, and choosing the CLI exit code are separate steps.
- Comments explain decisions and constraints—such as why only direct address-bar `<i>` elements count, why a failed request is not retried, or why the unknown-store control has a different expected response. They avoid restating obvious syntax.
- Docstrings describe the contract of reusable functions, including important inputs, outputs, and failure behavior.
- Tests use injected fetch, clock, and delay functions. This keeps the suite deterministic and offline while testing behavior rather than depending on the live website.
- Failure evidence is preserved. An engineer should be able to see which address failed, where it was advertised, the observed status and content type, a response prefix, and a body hash.
- Changes should stay within the agreed public-read scope. No credentials, private dashboards, write requests, or unapproved probing are needed for this check.

The goal is maintainable software that a person can review, explain, operate, and hand over—not code that only happens to pass once.

## What it checks

The checker reads these four public source pages:

- `https://www.banzena.com/`
- `https://www.banzena.com/pricing`
- `https://www.banzena.com/careers`
- `https://www.banzena.com/about`

On those pages, it collects address values only from direct `<i>` children of `div.lvbar` and `div.bz-shot-bar`. It ignores unrelated prose and nested lookalike elements, normalizes valid Banzena shop addresses and same-site paths, and deduplicates addresses advertised on multiple pages.

It then checks each discovered shop host and same-site path. The current agreement also includes two controls:

- `lduchen.banzena.com` is a known-good storefront control. If it is advertised, it is checked once and marked `known_good`; otherwise the checker adds it as a separate target.
- `not-a-shop-xyz.banzena.com` is an unknown-store negative control and must return the expected JSON 404 response.

The normal storefront contract is HTTP 200 with an HTML content type and without a recognized store-not-found JSON payload. The unknown-store control has the opposite contract: HTTP 404, JSON content type, and a not-found payload. Each same-site path must return HTTP 200 HTML without the recognized not-found payload.

## Request and safety behavior

- Requests are anonymous public HTTP GETs with the identifiable User-Agent `banzena-inventory-check/0.1`.
- The checker makes one fetch attempt per source or target URL and does not retry a failed request. A 0.2-second pause is inserted between fetch calls.
- The HTTP client uses a 15-second timeout. HTTP error responses are retained for contract validation; transport errors are reported as incomplete checks.
- The tool does not use credentials, dashboard routes, write methods, or private APIs. It does not alter Banzena data or deployment.
- Python's standard-library `urllib` redirect handling remains enabled. The report records the requested URL/host and response, but does not include a redirect-chain trace. A redirect therefore should not be interpreted as a separately audited request in the JSON evidence.

The one-attempt rule is deliberate: a transient failure is reported instead of silently generating extra traffic or making the result depend on an automatic retry.

## Requirements

- Python 3.11 or newer.
- Runtime: Python standard library only; no third-party runtime dependency.
- Build: setuptools 58 or newer, as declared in `pyproject.toml`.

## Install and run

From the repository root, install the package:

```bash
python3.11 -m pip install --no-build-isolation .
```

Run the agreed public check and print machine-readable JSON:

```bash
python3.11 -m banzena_inventory_check \
  --base https://www.banzena.com \
  --json
```

The module can also be run directly from a source checkout:

```bash
PYTHONPATH=src python3.11 -m banzena_inventory_check \
  --base https://www.banzena.com \
  --json
```

For concise human-readable output, omit `--json`. The output lists each target and its status; on a failed contract, it prints the source page, HTTP status, content type, fetch time, response prefix, and any error. JSON output is intended for CI, archiving, and downstream tooling.

## Exit codes

| Code | Meaning | Typical cause |
| --- | --- | --- |
| `0` | `pass` — every source and target satisfied its contract | Advertised hosts and paths return valid HTML; unknown control returns JSON 404 |
| `1` | `fail` — a response was received but violated its contract | Advertised storefront returned 404, non-HTML, or a recognized not-found body |
| `2` | `error` — the check could not establish complete evidence | Source page unavailable, transport failure, invalid source response, or undecodable source HTML |

A contract failure does not stop checks of the remaining targets, so one bad storefront does not hide other response evidence. A transport failure returns `2` because the inventory check is incomplete; it is not reported as a confirmed contract failure.

## Evidence format

The JSON report contains:

- the normalized base URL, the four source-page URLs, and the deduplicated inventory;
- for every checked host: its hostname, advertising pages, expected category, HTTP status, content type, first 200 response bytes, body SHA-256, fetch timestamp, and pass/fail status;
- for every checked same-site path: the requested URL and the same response evidence;
- an overall status, exit code, and error list.

Fetch times in reports are UTC in ISO 8601 form, for example `2026-09-24T02:09:35Z`. The report does not claim that an observed response will remain available later. Body hashes identify the exact response bytes observed; they do not prove who authored or changed the response.

## Tests and package checks

Run the offline unit tests from the repository root:

```bash
PYTHONPATH=src python3.11 -m unittest discover -s tests -v
```

The suite covers address extraction and normalization, deduplication, host and path response contracts, the negative control, evidence serialization, CLI diagnostics, transport failure handling, and the no-retry behavior. Test fetches are injected; the suite does not contact Banzena.

Useful local checks:

```bash
python3.11 -m compileall -q src tests
python3.11 -m pip wheel --no-build-isolation --no-deps --wheel-dir /tmp/banzena-wheel .
```

The delivery verification record also covers installation of the built wheel with `--no-index` and a smoke test of the installed module's `--help` command. Detailed run evidence is kept in the separate delivery evidence packet and is not included in this source repository.

## Code map

| File | Responsibility |
| --- | --- |
| `src/banzena_inventory_check/checker.py` | HTML address extraction, URL normalization, request pacing, response validation, evidence generation, and overall result |
| `src/banzena_inventory_check/__main__.py` | CLI argument parsing, text/JSON output, and process exit code |
| `src/banzena_inventory_check/__init__.py` | Small public Python API exporting `check_inventory` |
| `tests/test_checker.py` | Offline behavior and contract tests |
| `setup.py`, `pyproject.toml` | Package metadata and build configuration |
| Delivery evidence packet | Per-target run report, timestamp manifest, historical comparison, and local verification record; maintained separately from this source repository |
| `HANDOFF.md` | Scope, current result, evidence index, reproduction steps, and handover notes |

## Current acceptance snapshot

The preserved run completed on **2026-09-24, 10:09:21–10:10:05 Beijing time (UTC+8)**. It read four source pages and checked 8 normal shop hosts (7 advertised plus the known-good control), 5 advertised paths, and 1 unknown-store negative control. The 8 normal hosts and 5 paths returned HTTP 200 HTML; the negative control returned HTTP 404 JSON. The result was `PASS`, exit code `0`, with no errors.

This is a point-in-time observation, not a service-level guarantee. The separately maintained delivery packet contains the per-target report, exact run metadata, report SHA-256, and a before/after comparison that distinguishes the historical bundle time from HTTP server `Date` headers. Those evidence files are intentionally not part of this public source repository.

## License

This repository is distributed under the MIT License; see [`LICENSE`](LICENSE).
