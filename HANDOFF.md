# Banzena public inventory checker — delivery handoff

## Handover status

The agreed public inventory check has been implemented and a fresh point-in-time run passed. The source implementation, including the no-retry behavior, is on GitHub `main` at commit [`66bb9f4`](https://github.com/Tiee7/banzena-inventory-check/commit/66bb9f4f8a3b295d1835771730eaa7ff1aaa759c). This documentation is published in the repository. The detailed evidence packet is maintained separately and is not part of the public source repository. This handoff records the observed technical result; it does not represent customer acceptance.

## Agreed scope

The checker reads the four public source pages:

1. `https://www.banzena.com/`
2. `https://www.banzena.com/pricing`
3. `https://www.banzena.com/careers`
4. `https://www.banzena.com/about`

It extracts displayed address values from direct `<i>` children of `div.lvbar` and `div.bz-shot-bar`, deduplicates them, and checks each advertised shop host and same-site path. It includes `lduchen.banzena.com` as the known-good control and `not-a-shop-xyz.banzena.com` as the unknown-store negative control.

The normal shop-host contract is HTTP 200 HTML without a recognized not-found JSON payload. Same-site paths must return HTTP 200 HTML. The unknown-store control must return HTTP 404 JSON with a not-found body. The program reports:

- exit `0` when all source and target contracts pass;
- exit `1` when a response is observed but violates its contract;
- exit `2` when the check is incomplete, such as a source or target transport failure.

The check is read-only and anonymous. It uses no credentials, dashboard routes, write requests, or private APIs.

## Request behavior and written limit

Banzena specified one request per host. The implementation now performs one fetch attempt per source or target URL, spaces calls by 0.2 seconds, and never retries a failed request. A regression test proves a transient transport failure causes exactly one call. This was corrected before the final evidence run and is included in the remote commit above.

The standard-library `urllib` redirect handler is enabled. The run evidence captures the requested URL/host and returned response but does not record redirect-chain metadata. If redirect behavior needs to be treated as a separate acceptance condition, it should be confirmed before interpreting that part of a run as independently audited.

## Fresh public run

The final evidence run used the remote implementation commit above and ran from **2026-09-24 10:09:21 to 10:10:05 Beijing time (UTC+8)**, equivalent to **2026-09-24 02:09:21Z–02:10:05Z**. It lasted 44 seconds and exited `0` with no errors.

| Check | Count | Result |
| --- | ---: | --- |
| Public source pages | 4 | Read successfully |
| Advertised shop hosts | 7 | HTTP 200 HTML |
| Known-good shop control | 1 | HTTP 200 HTML |
| Advertised same-site paths | 5 | HTTP 200 HTML |
| Unknown-store negative control | 1 | HTTP 404 JSON |
| Target evidence records | 14 | All timestamps within run bounds |

The two classes of “8 shops” are reported explicitly: seven hosts had `expected=advertised`, while the eighth normal shop host was tagged `known_good`. The unknown negative control is an additional ninth host evidence record. There are 14 target records total: 9 host records plus 5 path records. The 4 source-page requests are recorded in the run's `pages` field, not included in the 14 target records.

The report SHA-256 is:

```text
fe108e64c5c54baf0f8745ec55ec0789d26f687d22fe25cc16f0397f84490c7f
```

Every target's `fetched_at` value was checked against the manifest's start and end times. UTC timestamps were also checked against their Beijing UTC+8 representations.

## Before-and-after evidence

The preserved baseline from 2026-09-20 shows District Threads and Lumen Studio returning HTTP 404 JSON with the same 27-byte `{"error":"Store not found"}` body and SHA-256 `6180b9b7e10f06b3f2bf9e03f370cb9829762772f9f677350a811c3ba277c41d`.

The original evidence bundle's observation metadata says **2026-09-20 01:49:59 Beijing time**. Individual saved HTTP `Date` headers instead say District **2026-09-19 17:49:27Z / 2026-09-20 01:49:27+08:00** and Lumen **2026-09-19 17:49:28Z / 2026-09-20 01:49:28+08:00**. These are distinct clocks and have not been substituted for one another. The current run later observed both hosts returning valid HTML. That comparison documents the responses at those times; it does not assert that this checker caused any repair or guarantee future availability.

The separate delivery evidence packet contains the readable comparison and preserved baseline fields, with original source references.

## Reproduce the check

From the repository root with Python 3.11:

```bash
python3.11 -m pip install --no-build-isolation .
python3.11 -m banzena_inventory_check --base https://www.banzena.com --json
```

To run directly from a checkout without installing:

```bash
PYTHONPATH=src python3.11 -m banzena_inventory_check --base https://www.banzena.com --json
```

The command contacts the live public site. The unit tests below are offline and do not contact Banzena:

```bash
PYTHONPATH=src python3.11 -m unittest discover -s tests -v
```

## Verification completed

The Python 3.11 verification record in the separate delivery packet records successful:

- compilation of `src` and `tests`;
- all 10 offline unit tests;
- wheel build;
- wheel installation with `--no-index` (no package-index/network access);
- installed module `--help` smoke test.

The suite includes tests for the no-retry behavior and exit-code distinction. Timestamp strings used by deterministic test fixtures are `2026-09-24T01:58:03Z` (09:58:03 Beijing time); these are fixed test inputs, not execution timestamps.

## Evidence index

| File | What it contains |
| --- | --- |
| `public-run-20260924.json` | Per-host and per-path response evidence, advertising source, UTC fetch time, response prefix, body hash, status, and contract category; separate packet |
| `delivery-manifest.json` | Exact command, implementation commit, UTC and Beijing run bounds, counts, exit status, and report SHA-256; separate packet |
| `before-baseline-20260920.json` | Preserved original baseline fields with separate bundle time and per-response server `Date` values; separate packet |
| `before-after.md` | Human-readable comparison with causation and timestamp caveats; separate packet |
| `verification-20260924.txt` | Python 3.11 test, build, install, and CLI verification output; separate packet |

## Commercial handoff

Commercial terms, invoicing, and payment coordination are handled separately from this public technical repository and are intentionally omitted here.

## Maintainer handoff

The project favors code that a person can understand and maintain. When extending it, preserve the small responsibilities and explanatory comments around scope, controls, and failure behavior. Add tests for behavior changes before or alongside implementation; prefer injected fetch/time/sleep dependencies over tests that require live network access. Keep comments focused on why a decision exists, rather than paraphrasing the next line. See [`README.md`](README.md) for the development principles, code map, operating commands, report fields, and limits.
