"""Check that shops and paths advertised by Banzena respond as expected.

The checker only reads public pages with anonymous HTTP GET requests. It does
not change the Banzena site; instead, it records enough response evidence to
make a failed inventory check diagnosable in a local run or CI job.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


_HOST_RE = re.compile(
    r"^(?:https?://)?"
    r"(?P<host>(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*banzena\.com)"
    r"(?P<path>/[^\s?#]*)?(?:\?[^\s#]*)?(?:#[^\s]*)?$",
    re.IGNORECASE,
)
PUBLIC_PATHS = ("/", "/pricing", "/careers", "/about")


class SourceFailure(RuntimeError):
    """The source could not be fetched or decoded, so its contract is unknown."""


class ContractFailure(RuntimeError):
    """A fetched response violates the advertised-host contract.

    Keep the response evidence on the exception so the caller can include the
    failed response in the final report instead of losing useful diagnostics.
    """

    def __init__(self, message: str, evidence: dict | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


class _InventoryParser(HTMLParser):
    """Collect values only from the small address-bar components in the pages.

    A stack is kept because ``HTMLParser`` emits nested start/end events. The
    capture depth lets us finish one ``<i>`` value at its matching close tag,
    while ignoring surrounding explanatory prose and unrelated page content.
    """

    _COMPONENT_CLASSES = {"lvbar", "bz-shot-bar"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._stack = []
        self._capture = None
        self.values = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        parent = self._stack[-1] if self._stack else None
        # The advertised value is the direct <i> child of one of these bars;
        # nearby labels and links are intentionally not treated as inventory.
        if tag.lower() == "i" and parent and parent[0] == "div":
            classes = set((parent[1].get("class") or "").split())
            if classes & self._COMPONENT_CLASSES:
                self._capture = {"depth": len(self._stack) + 1, "parts": []}
        self._stack.append((tag.lower(), attrs))

    def handle_endtag(self, tag):
        tag = tag.lower()
        # Match the <i> we opened, rather than closing on a nested element.
        if self._capture and tag == "i" and len(self._stack) == self._capture["depth"]:
            self.values.append(" ".join(self._capture["parts"]).strip())
            self._capture = None
        if self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if self._capture:
            self._capture["parts"].append(data)


def _target_from_value(value: str, source_url: str) -> str | None:
    """Normalize one bar value and reject values outside Banzena's inventory.

    Slash-prefixed values are same-site paths. Other values must parse as a
    Banzena host (optionally with a path); arbitrary prose, external hosts, and
    the corporate site's own root are not shop targets.
    """
    normalized = " ".join(value.split()).strip()
    if normalized.startswith("/"):
        # Resolve relative paths against the page that advertised them, then
        # retain the query string because it can be part of the public route.
        parsed = urlsplit(urljoin(source_url, normalized))
        host = (parsed.hostname or "").lower().rstrip(".")
        path = parsed.path or "/"
        query = parsed.query
    else:
        # Bare shop domains are accepted as HTTPS URLs. The host regex keeps
        # values such as explanatory sentences from becoming false targets.
        candidate = normalized if re.match(r"^https?://", normalized, re.IGNORECASE) else "https://" + normalized
        match = _HOST_RE.fullmatch(candidate)
        if not match:
            return None
        host = match.group("host").lower().rstrip(".")
        path = match.group("path") or "/"
        query = ""
        if "?" in normalized:
            query = normalized.split("?", 1)[1].split("#", 1)[0]

    if host in ("banzena.com", "www.banzena.com") and path == "/":
        # The main site is a source of inventory, not itself a shop listing.
        return None
    if host not in ("banzena.com", "www.banzena.com") and not host.endswith(".banzena.com"):
        return None
    return "https://%s%s%s" % (host, path, ("?" + query) if query else "")


def extract_inventory(html: str, source_url: str) -> list[str]:
    """Return unique shop hosts and same-site paths advertised on one page."""
    parser = _InventoryParser()
    parser.feed(html)
    parser.close()
    targets = []
    for value in parser.values:
        target = _target_from_value(value, source_url)
        if target and target not in targets:
            targets.append(target)
    return targets


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _host_evidence(hostname, advertised_by, status, content_type, body, fetched_at, expected):
    """Build stable, compact diagnostics for a shop-host response."""
    return {
        "hostname": hostname,
        "advertised_by": advertised_by,
        "expected": expected,
        "status_code": status,
        "content_type": content_type,
        "first_bytes": body[:200].decode("utf-8", errors="replace"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "fetched_at": fetched_at,
    }


def _path_evidence(url, advertised_by, status, content_type, body, fetched_at):
    """Build the same response diagnostics for an advertised site path."""
    return {
        "url": url,
        "advertised_by": advertised_by,
        "expected": "advertised_path",
        "status_code": status,
        "content_type": content_type,
        "first_bytes": body[:200].decode("utf-8", errors="replace"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "fetched_at": fetched_at,
    }


def _looks_like_not_found_json(content_type: str, body: bytes) -> bool:
    """Catch a store-missing payload served through an otherwise misleading response."""
    if "json" not in content_type.lower():
        return False
    text = body[:4096].decode("utf-8", errors="replace").lower()
    return "not found" in text or "store-not-found" in text or "store_not_found" in text


def inspect_host_response(
    hostname: str,
    advertised_by: list[str],
    status: int,
    content_type: str,
    body: bytes,
    fetched_at: str,
    expected: str,
) -> dict:
    """Validate one shop host and return evidence or raise with that evidence.

    The negative-control host has a different contract: it should produce the
    expected JSON 404. All advertised and known-good shops must instead serve
    ordinary HTML with status 200.
    """
    evidence = _host_evidence(
        hostname, advertised_by, status, content_type, body, fetched_at, expected
    )
    content_type_lower = content_type.lower()
    if expected == "unknown":
        # The negative control confirms that unknown shops are rejected using
        # the application's recognized not-found JSON response.
        valid = status == 404 and "json" in content_type_lower and _looks_like_not_found_json(content_type, body)
        if not valid:
            raise ContractFailure(
                "%s must return JSON 404 for the unknown-store control" % hostname,
                evidence,
            )
        evidence["status"] = "pass"
        return evidence

    # A JSON not-found body must fail even if a proxy reports HTTP 200.
    valid = (
        status == 200
        and content_type_lower.startswith("text/html")
        and not _looks_like_not_found_json(content_type, body)
    )
    if not valid:
        raise ContractFailure(
            "%s must return non-error HTML 200" % hostname,
            evidence,
        )
    evidence["status"] = "pass"
    return evidence


def inspect_path_response(url, advertised_by, status, content_type, body, fetched_at):
    """Require an advertised same-site path to serve non-error HTML 200."""
    evidence = _path_evidence(url, advertised_by, status, content_type, body, fetched_at)
    valid = (
        status == 200
        and content_type.lower().startswith("text/html")
        and not _looks_like_not_found_json(content_type, body)
    )
    if not valid:
        raise ContractFailure("%s must return non-error HTML 200" % url, evidence)
    evidence["status"] = "pass"
    return evidence


def fetch_url(url: str):
    """Fetch a public URL with an identifiable User-Agent and bounded timeout.

    HTTP error statuses are returned with their bodies so contract validation
    can distinguish an expected 404 from a transport failure.
    """
    request = Request(url, headers={"User-Agent": "banzena-inventory-check/0.1"})
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, response.headers.get("content-type", ""), response.read()
    except HTTPError as exc:
        body = exc.read()
        return exc.code, exc.headers.get("content-type", ""), body
    except (OSError, URLError, TimeoutError) as exc:
        raise SourceFailure("could not fetch %s: %s" % (url, exc)) from exc


def _base_url(base: str) -> str:
    """Validate the input origin and discard any path/query supplied by caller."""
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SourceFailure("base must be an http(s) URL")
    return "%s://%s" % (parsed.scheme, parsed.netloc)


def check_inventory(base: str, fetch=fetch_url, now=_now_iso, sleep=time.sleep, delay=0.2) -> dict:
    """Check source pages and every advertised target, returning a CI-ready report.

    Exit codes are represented in the report: 0 means all contracts passed,
    1 means a target violated its response contract, and 2 means the checker
    could not complete reliably (for example, a source page was unavailable).
    ``fetch``, ``now`` and ``sleep`` are injectable to make tests deterministic
    and to avoid real network requests in the offline test suite.
    """
    request_count = 0

    def fetch_polite(url):
        """Space one anonymous request per URL without retrying the target."""
        nonlocal request_count
        # Keep the agreed request spacing, and never issue a second request
        # after a transport failure: each advertised URL is checked once.
        if request_count:
            sleep(delay)
        request_count += 1
        return fetch(url)

    try:
        base = _base_url(base)
        pages = []
        # These are the agreed public catalog pages; failures here prevent a
        # trustworthy inventory, so they produce exit code 2.
        for path in PUBLIC_PATHS:
            page_url = base if path == "/" else base + path
            status, content_type, body = fetch_polite(page_url)
            if status != 200 or not content_type.lower().startswith("text/html"):
                raise SourceFailure("public page did not return HTML 200: %s" % page_url)
            pages.append((page_url, body.decode("utf-8")))
        advertised_by = {}
        for page_url, html in pages:
            for target in extract_inventory(html, page_url):
                advertised_by.setdefault(target, []).append(page_url)
        inventory = sorted(advertised_by)
        # Keep the advertised known-good shop in the inventory and add it as a
        # separate control only if none of the source pages listed it.
        targets = [
            (
                target,
                "known_good"
                if urlsplit(target).hostname == "lduchen.banzena.com" and urlsplit(target).path == "/"
                else "advertised",
            )
            for target in inventory
        ]
        known_good_url = "https://lduchen.banzena.com/"
        if known_good_url not in advertised_by:
            targets.append((known_good_url, "known_good"))
        # This negative control should remain absent from all source pages.
        targets.append(("https://not-a-shop-xyz.banzena.com/", "unknown"))
    except (UnicodeError, SourceFailure) as exc:
        # Without all source documents, target coverage would be incomplete.
        return {
            "status": "error",
            "exit_code": 2,
            "base": base,
            "pages": [],
            "hosts": [],
            "paths": [],
            "errors": [str(exc)],
        }

    report_hosts = []
    report_paths = []
    failures = []
    for target, expected in targets:
        parsed_target = urlsplit(target)
        hostname = parsed_target.hostname or target
        try:
            response_status, response_type, response_body = fetch_polite(target)
            if hostname in ("banzena.com", "www.banzena.com"):
                report_paths.append(
                    inspect_path_response(
                        target,
                        advertised_by.get(target, []),
                        response_status,
                        response_type,
                        response_body,
                        now(),
                    )
                )
            else:
                report_hosts.append(
                    inspect_host_response(
                        hostname,
                        advertised_by.get(target, []),
                        response_status,
                        response_type,
                        response_body,
                        now(),
                        expected,
                    )
                )
        except ContractFailure as exc:
            # Contract failures are recorded and the remaining targets still
            # run, so one bad shop does not hide other evidence.
            evidence = exc.evidence or {"hostname": hostname, "expected": expected}
            evidence["status"] = "fail"
            evidence["error"] = str(exc)
            if hostname in ("banzena.com", "www.banzena.com"):
                report_paths.append(evidence)
            else:
                report_hosts.append(evidence)
            failures.append(str(exc))
        except SourceFailure as exc:
            # A transport error means this check is incomplete; stop here and
            # use exit code 2 rather than misreporting it as a contract failure.
            evidence = {
                "url": target,
                "hostname": hostname,
                "advertised_by": advertised_by.get(target, []),
                "expected": expected,
                "status": "error",
                "error": str(exc),
                "fetched_at": now(),
            }
            if hostname in ("banzena.com", "www.banzena.com"):
                report_paths.append(evidence)
            else:
                report_hosts.append(evidence)
            return {
                "status": "error",
                "exit_code": 2,
                "base": base,
                "pages": [page_url for page_url, _ in pages],
                "inventory": inventory,
                "hosts": report_hosts,
                "paths": report_paths,
                "errors": [str(exc)],
            }

    # Distinguish an observed bad response (1) from inability to observe it (2).
    return {
        "status": "pass" if not failures else "fail",
        "exit_code": 0 if not failures else 1,
        "base": base,
        "pages": [page_url for page_url, _ in pages],
        "inventory": inventory,
        "hosts": report_hosts,
        "paths": report_paths,
        "errors": failures,
    }
