# Before-and-after response evidence

This compares the preserved public baseline with the fresh acceptance run. It records observed responses only; it does not claim that this checker caused Banzena's repair.

## Before: 2026-09-20

The original evidence bundle records capture at **2026-09-20 01:49:59 Beijing time (UTC+8)**. The two affected hosts returned HTTP 404 `application/json`, each with the 27-byte body `{"error":"Store not found"}` and SHA-256 `6180b9b7e10f06b3f2bf9e03f370cb9829762772f9f677350a811c3ba277c41d`.

The saved response headers give per-response server `Date` values: District Threads at **2026-09-19 17:49:27Z / 2026-09-20 01:49:27+08:00**; Lumen Studio at **2026-09-19 17:49:28Z / 2026-09-20 01:49:28+08:00**. These are kept distinct from the bundle's 01:49:59 local observation-record time. The `harvestroot` and `lduchen` controls returned HTTP 200 `text/html` at server Date 17:49:28Z and 17:49:27Z respectively. Details and body hashes are in [`before-baseline-20260920.json`](before-baseline-20260920.json).

## After: 2026-09-24

The final checker run started at **2026-09-24 10:09:21 Beijing time** and finished at **10:10:05** (02:09:21Z–02:10:05Z). It read the four agreed source pages and recorded 8 advertised shop hosts plus 5 advertised paths. All 8 hosts and 5 paths returned HTTP 200 `text/html`; the separate unknown-store negative control returned HTTP 404 `application/json`. Overall: `PASS`, exit code `0`.

Per-target UTC times, advertising pages, response prefixes and body SHA-256 values are in [`public-run-20260924.json`](public-run-20260924.json). The run bounds and report hash are in [`delivery-manifest.json`](delivery-manifest.json). Every one of the 14 target evidence timestamps falls between the recorded run start and finish. The recorded report SHA-256 is `fe108e64c5c54baf0f8745ec55ec0789d26f687d22fe25cc16f0397f84490c7f`.

The customer had already reported the two hosts fixed in a 2026-09-20 email. The later run independently verifies their current public responses and the agreed controls; it does not attribute the fix to this checker.
