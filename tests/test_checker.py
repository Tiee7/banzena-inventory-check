import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from banzena_inventory_check.checker import (
    ContractFailure,
    SourceFailure,
    check_inventory,
    extract_inventory,
    inspect_host_response,
)


class InventoryExtractionTests(unittest.TestCase):
    def test_reads_advertised_hosts_only_from_address_bar_i_elements(self):
        html = """
        <div class="lvbar"><i>district-threads.banzena.com</i></div>
        <div class="bz-shot-bar"><i>https://ember-hearth.banzena.com</i></div>
        <div class="lvbar"><span><i>nested-ignored.banzena.com</i></span></div>
        <p>A free yourshop.banzena.com address with automatic SSL</p>
        """

        self.assertEqual(
            [
                "https://district-threads.banzena.com/",
                "https://ember-hearth.banzena.com/",
            ],
            extract_inventory(html, "https://www.banzena.com"),
        )

    def test_reads_advertised_site_paths_in_the_same_components(self):
        html = """
        <div class="lvbar"><i>banzena.com/examples/carat</i></div>
        <div class="lvbar"><i>/crate</i></div>
        <div class="bz-shot-bar"><i>https://www.banzena.com/examples/dew</i></div>
        <div class="bz-shot-bar"><i>/stamp</i></div>
        <div class="lvbar"><i>/tempo</i></div>
        <p>/not-an-address</p>
        """

        self.assertEqual(
            [
                "https://banzena.com/examples/carat",
                "https://www.banzena.com/crate",
                "https://www.banzena.com/examples/dew",
                "https://www.banzena.com/stamp",
                "https://www.banzena.com/tempo",
            ],
            extract_inventory(html, "https://www.banzena.com"),
        )

    def test_duplicate_advertisements_are_deduplicated(self):
        html = (
            '<div class="lvbar"><i>lduchen.banzena.com</i></div>'
            '<div class="bz-shot-bar"><i>lduchen.banzena.com</i></div>'
        )
        self.assertEqual(["https://lduchen.banzena.com/"], extract_inventory(html, "https://www.banzena.com"))


class HostInspectionTests(unittest.TestCase):
    def test_advertised_host_requires_html_and_non_error_body(self):
        evidence = inspect_host_response(
            hostname="lduchen.banzena.com",
            advertised_by=["https://www.banzena.com"],
            status=200,
            content_type="text/html; charset=utf-8",
            body=b"<html><title>shop</title></html>",
            fetched_at="2026-09-24T01:58:03Z",
            expected="advertised",
        )
        self.assertEqual("pass", evidence["status"])
        self.assertEqual("lduchen.banzena.com", evidence["hostname"])
        self.assertIn("first_bytes", evidence)

    def test_unknown_control_requires_json_404(self):
        evidence = inspect_host_response(
            hostname="not-a-shop-xyz.banzena.com",
            advertised_by=[],
            status=404,
            content_type="application/json",
            body=b'{"error":"store not found"}',
            fetched_at="2026-09-24T01:58:03Z",
            expected="unknown",
        )
        self.assertEqual("pass", evidence["status"])

    def test_advertised_404_is_contract_failure(self):
        with self.assertRaises(ContractFailure):
            inspect_host_response(
                hostname="lduchen.banzena.com",
                advertised_by=["https://www.banzena.com"],
                status=404,
                content_type="application/json",
                body=b'{"error":"store not found"}',
                fetched_at="2026-09-24T01:58:03Z",
                expected="advertised",
            )


class InventoryCheckTests(unittest.TestCase):
    def test_check_inventory_returns_ci_report_without_network_in_test(self):
        home = """
        <div class="lvbar"><i>district-threads.banzena.com</i></div>
        <div class="bz-shot-bar"><i>ember-hearth.banzena.com</i></div>
        <div class="lvbar"><i>harvestroot.banzena.com</i></div>
        <div class="lvbar"><i>banzena.com/examples/carat</i></div>
        <div class="lvbar"><i>/crate</i></div>
        <div class="lvbar"><i>/dew</i></div>
        <div class="lvbar"><i>/stamp</i></div>
        <div class="lvbar"><i>/tempo</i></div>
        <p>yourshop.banzena.com</p>
        """
        pricing = (
            '<div class="bz-shot-bar"><i>harvestroot.banzena.com</i></div>'
            '<div class="bz-shot-bar"><i>lduchen.banzena.com</i></div>'
        )
        careers = '<div class="lvbar"><i>lumen-studio.banzena.com</i></div>'
        about = (
            '<div class="lvbar"><i>north-ridge-roasters.banzena.com</i></div>'
            '<div class="lvbar"><i>pixel-and-press.banzena.com</i></div>'
            '<div class="bz-shot-bar"><i>soft-skin-society.banzena.com</i></div>'
        )
        fetch_calls = []
        delay_calls = []

        def fetch(url):
            fetch_calls.append(url)
            if url == "https://www.banzena.com":
                return 200, "text/html", home.encode()
            if url == "https://www.banzena.com/pricing":
                return 200, "text/html", pricing.encode()
            if url == "https://www.banzena.com/careers":
                return 200, "text/html", careers.encode()
            if url == "https://www.banzena.com/about":
                return 200, "text/html", about.encode()
            if "not-a-shop-xyz" in url:
                return 404, "application/json", b'{"error":"store not found"}'
            return 200, "text/html", b"<html>shop</html>"

        report = check_inventory(
            base="https://www.banzena.com",
            fetch=fetch,
            now=lambda: "2026-09-24T01:58:03Z",
            sleep=delay_calls.append,
        )

        self.assertEqual("pass", report["status"])
        self.assertEqual(0, report["exit_code"])
        self.assertEqual(
            sorted([
                "https://banzena.com/examples/carat",
                "https://www.banzena.com/crate",
                "https://www.banzena.com/dew",
                "https://www.banzena.com/stamp",
                "https://www.banzena.com/tempo",
                "https://district-threads.banzena.com/",
                "https://ember-hearth.banzena.com/",
                "https://harvestroot.banzena.com/",
                "https://lduchen.banzena.com/",
                "https://lumen-studio.banzena.com/",
                "https://north-ridge-roasters.banzena.com/",
                "https://pixel-and-press.banzena.com/",
                "https://soft-skin-society.banzena.com/",
            ]),
            report["inventory"],
        )
        self.assertEqual(
            {"/", "/pricing", "/careers", "/about"},
            {url.removeprefix("https://www.banzena.com") or "/" for url in report["pages"]},
        )
        self.assertEqual(
            [
                "https://banzena.com/examples/carat",
                "https://www.banzena.com/crate",
                "https://www.banzena.com/dew",
                "https://www.banzena.com/stamp",
                "https://www.banzena.com/tempo",
            ],
            [item["url"] for item in report["paths"]],
        )
        self.assertEqual(18, len(fetch_calls))
        self.assertEqual(17, len(delay_calls))
        self.assertEqual(
            "known_good",
            next(item["expected"] for item in report["hosts"] if item["hostname"] == "lduchen.banzena.com"),
        )
        self.assertEqual(
            ["https://www.banzena.com"],
            next(item["advertised_by"] for item in report["hosts"] if item["hostname"] == "ember-hearth.banzena.com"),
        )
        self.assertEqual(
            ["https://www.banzena.com/careers"],
            next(item["advertised_by"] for item in report["hosts"] if item["hostname"] == "lumen-studio.banzena.com"),
        )
        json.dumps(report)

    def test_transient_get_failure_is_not_retried(self):
        fetch_calls = []

        def fetch(url):
            fetch_calls.append(url)
            raise SourceFailure("temporary TLS EOF")

        report = check_inventory(
            base="https://www.banzena.com",
            fetch=fetch,
            now=lambda: "2026-09-24T01:58:03Z",
        )

        self.assertEqual("error", report["status"])
        self.assertEqual(2, report["exit_code"])
        self.assertEqual(["https://www.banzena.com"], fetch_calls)

    def test_fetch_failure_is_exit_code_two(self):
        def fetch(url):
            raise SourceFailure("timeout")

        report = check_inventory(
            base="https://www.banzena.com",
            fetch=fetch,
            now=lambda: "2026-09-24T01:58:03Z",
            sleep=lambda _: None,
        )
        self.assertEqual("error", report["status"])
        self.assertEqual(2, report["exit_code"])

    def test_default_cli_prints_failure_evidence_for_advertised_paths(self):
        from banzena_inventory_check.__main__ import main

        report = {
            "status": "fail",
            "exit_code": 1,
            "errors": ["https://www.banzena.com/examples/carat must return non-error HTML 200"],
            "hosts": [],
            "paths": [
                {
                    "url": "https://www.banzena.com/examples/carat",
                    "advertised_by": ["https://www.banzena.com"],
                    "status": "fail",
                    "status_code": 404,
                    "content_type": "application/json",
                    "first_bytes": '{"error":"not found"}',
                    "fetched_at": "2026-09-24T01:58:03Z",
                    "error": "path did not meet the HTML 200 contract",
                }
            ],
        }
        output = StringIO()
        with patch("banzena_inventory_check.__main__.check_inventory", return_value=report):
            with redirect_stdout(output):
                exit_code = main(["--base", "https://www.banzena.com"])

        self.assertEqual(1, exit_code)
        for expected in ("https://www.banzena.com/examples/carat", "404", "application/json", '{"error":"not found"}'):
            self.assertIn(expected, output.getvalue())


if __name__ == "__main__":
    unittest.main()
