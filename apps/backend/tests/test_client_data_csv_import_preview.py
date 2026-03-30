"""Tests for the CSV import preview and confirm services."""

import os
import unittest

from app.services.client_data_csv_import_service import import_csv_rows, parse_csv_for_preview


class CsvImportPreviewServiceTests(unittest.TestCase):

    def test_valid_csv_all_columns(self):
        """Send a valid CSV with all columns → 200, all rows valid."""
        csv_content = (
            "Săptămâna;Data vânzare;Lead-uri;Telefoane;Custom Value 1;Custom Value 2;"
            "Custom Value 3;Custom Value 4;Custom Value 5;Vânzări;Preț vânzare;Preț actual;Profit Brut;Sursa\n"
            "9;2026-03-01;10;5;3;2;100.50;200;50.25;4;1500.00;1200.00;300.00;google_ads\n"
            "10;2026-03-08;15;8;4;3;150.00;250;75.50;6;2000.00;1800.00;200.00;meta_ads\n"
        )
        result = parse_csv_for_preview(csv_content.encode("utf-8"))

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["valid"], 2)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(len(result["columns_detected"]), 14)
        self.assertEqual(result["rows"][0]["status"], "valid")
        self.assertEqual(result["rows"][0]["data"]["week"], 9)
        self.assertEqual(result["rows"][0]["data"]["metric_date"], "2026-03-01")
        self.assertEqual(result["rows"][0]["data"]["leads"], 10)
        self.assertEqual(result["rows"][0]["data"]["source"], "google_ads")

    def test_missing_date_column_marks_error(self):
        """CSV with a row missing Data vânzare → that row has status: error."""
        csv_content = (
            "Lead-uri;Telefoane\n"
            "10;5\n"
        )
        result = parse_csv_for_preview(csv_content.encode("utf-8"))

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["valid"], 0)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["rows"][0]["status"], "error")
        self.assertIn("Lipsește Data vânzare sau Săptămâna", result["rows"][0]["error_message"])

    def test_non_csv_content_returns_error(self):
        """Send a file without CSV structure → ValueError."""
        # A file with no recognizable headers at all
        bad_content = b"This is just some random text without any structure whatsoever"
        with self.assertRaises(ValueError) as ctx:
            parse_csv_for_preview(bad_content)
        self.assertIn("Nicio coloană", str(ctx.exception))

    def test_semicolon_delimiter_excel_romanian(self):
        """CSV with ; delimiter (Romanian Excel export) → parses correctly."""
        csv_content = (
            "Saptamana;Data vanzare;Leaduri;Telefoane;Vanzari;Sursa\n"
            "9;01/03/2026;10;5;4;direct\n"
            "10;08/03/2026;15;8;6;meta_ads\n"
        )
        result = parse_csv_for_preview(csv_content.encode("utf-8"))

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["valid"], 2)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["rows"][0]["data"]["week"], 9)
        self.assertEqual(result["rows"][0]["data"]["metric_date"], "2026-03-01")

    def test_comma_delimiter(self):
        """CSV with , delimiter → parses correctly."""
        csv_content = (
            "Săptămâna,Data vânzare,Lead-uri\n"
            "9,2026-03-01,10\n"
        )
        result = parse_csv_for_preview(csv_content.encode("utf-8"))

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["rows"][0]["data"]["leads"], 10)

    def test_too_many_rows(self):
        """CSV with > 500 rows → ValueError."""
        header = "Săptămâna;Data vânzare\n"
        rows = "".join(f"{i};2026-03-01\n" for i in range(501))
        csv_content = header + rows
        with self.assertRaises(ValueError) as ctx:
            parse_csv_for_preview(csv_content.encode("utf-8"))
        self.assertIn("500 rânduri", str(ctx.exception))

    def test_file_too_large(self):
        """CSV > 5MB → ValueError."""
        large_content = b"Saptamana;Data vanzare\n" + b"1;2026-03-01\n" * (600_000)
        if len(large_content) <= 5 * 1024 * 1024:
            # Make sure it's actually over 5MB
            large_content = b"x" * (5 * 1024 * 1024 + 1)
        with self.assertRaises(ValueError) as ctx:
            parse_csv_for_preview(large_content)
        self.assertIn("5MB", str(ctx.exception))

    def test_empty_file(self):
        """Empty file → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            parse_csv_for_preview(b"")
        self.assertIn("gol", str(ctx.exception))

    def test_header_only_no_data_rows(self):
        """CSV with only header → ValueError."""
        csv_content = b"Saptamana;Data vanzare;Lead-uri\n"
        with self.assertRaises(ValueError) as ctx:
            parse_csv_for_preview(csv_content)
        self.assertIn("nu conține rânduri", str(ctx.exception))

    def test_case_insensitive_headers(self):
        """Headers with mixed case → maps correctly."""
        csv_content = (
            "SAPTAMANA;DATA VANZARE;LEAD-URI\n"
            "9;2026-03-01;10\n"
        )
        result = parse_csv_for_preview(csv_content.encode("utf-8"))
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["rows"][0]["data"]["week"], 9)

    def test_decimal_with_comma_in_values(self):
        """Decimal values with comma (European format) in comma-delimited CSV with semicolons."""
        csv_content = (
            "Saptamana;Data vanzare;Pret vanzare\n"
            "9;2026-03-01;1500,50\n"
        )
        result = parse_csv_for_preview(csv_content.encode("utf-8"))
        self.assertEqual(result["valid"], 1)
        self.assertEqual(result["rows"][0]["data"]["sale_price_amount"], "1500.50")

    def test_utf8_bom(self):
        """CSV with UTF-8 BOM → parses correctly."""
        csv_content = "\ufeffSăptămâna;Data vânzare\n9;2026-03-01\n"
        result = parse_csv_for_preview(csv_content.encode("utf-8-sig"))
        self.assertEqual(result["valid"], 1)

    def test_partial_valid_rows(self):
        """Mix of valid and invalid rows."""
        csv_content = (
            "Saptamana;Data vanzare;Lead-uri\n"
            "9;2026-03-01;10\n"
            ";;5\n"
            "11;2026-03-15;20\n"
        )
        result = parse_csv_for_preview(csv_content.encode("utf-8"))
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["valid"], 2)
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["rows"][1]["status"], "error")


class CsvImportConfirmServiceTests(unittest.TestCase):

    def test_empty_rows_raises(self):
        """import_csv_rows with empty rows list → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            import_csv_rows(client_id=1, rows=[])
        self.assertIn("Nu există rânduri", str(ctx.exception))

    def test_columns_mapping_present_in_preview(self):
        """Preview response includes columns_mapping parallel to columns_detected."""
        csv_content = (
            "Săptămâna;Data vânzare;Lead-uri\n"
            "9;2026-03-01;10\n"
        )
        result = parse_csv_for_preview(csv_content.encode("utf-8"))
        self.assertIn("columns_mapping", result)
        self.assertEqual(len(result["columns_mapping"]), len(result["columns_detected"]))
        self.assertEqual(result["columns_mapping"][0], "week")
        self.assertEqual(result["columns_mapping"][1], "metric_date")
        self.assertEqual(result["columns_mapping"][2], "leads")


if __name__ == "__main__":
    unittest.main()
