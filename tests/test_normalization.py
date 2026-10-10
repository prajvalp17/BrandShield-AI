import unittest

from normalization import (
    normalize_contact_number,
    normalize_package_id,
    normalize_redirect_url,
)


class NormalizationTests(unittest.TestCase):
    def test_package_id_preserves_dots_and_hyphens(self):
        self.assertEqual(
            normalize_package_id(" Com.Example-App "),
            "com.example-app",
        )

    def test_contact_number_removes_formatting(self):
        self.assertEqual(
            normalize_contact_number("+91 90000-11111"),
            "919000011111",
        )

    def test_redirect_url_preserves_full_path_and_query(self):
        self.assertEqual(
            normalize_redirect_url("HTTPS://Example.COM/path?a=1"),
            "https://example.com/path?a=1",
        )

    def test_missing_values_stay_unknown(self):
        self.assertIsNone(normalize_package_id(None))
        self.assertIsNone(normalize_contact_number(None))
        self.assertIsNone(normalize_redirect_url(None))


if __name__ == "__main__":
    unittest.main()