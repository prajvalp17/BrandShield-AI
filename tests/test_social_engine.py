import unittest

from social_engine import evaluate


class SocialEngineTests(unittest.TestCase):
    def setUp(self):
        self.brand = {
            "brand_id": "brand_01",
            "name": "Brand",
            "official_handles": {
                "Instagram": ["@officialbrand"],
            },
        }
        self.candidate = {
            "entity_id": "soc_04",
            "target_type": "social_profile",
            "brand_id": "brand_01",
            "platform": "Instagram",
            "username": "@brand_support",
            "display_name": "Brand Support",
            "bio": "DM us to verify your account",
            "account_age_days": 12,
            "contact_number": "+91 90000 11111",
            "redirect_url": "https://example.com/verify",
            "evidence_source": "simulated",
        }

    def test_output_has_contract_fields_and_signals(self):
        result = evaluate(self.brand, self.candidate)

        self.assertEqual(result["entity_id"], "soc_04")
        self.assertEqual(result["target_type"], "social_profile")
        self.assertEqual(
            set(result["signals"]),
            {"handle_similarity", "name_similarity", "scam_phrase", "account_age"},
        )

        for signal in result["signals"].values():
            self.assertIn(signal["category"], {"identity", "content", "metadata"})
            self.assertTrue(
                signal["value"] is None
                or 0.0 <= signal["value"] <= 1.0
            )

    def test_exact_official_handle_is_excluded(self):
        candidate = dict(self.candidate)
        candidate["username"] = "@officialbrand"

        result = evaluate(self.brand, candidate)

        self.assertTrue(result["is_official"])
        self.assertEqual(result["signals"], {})
        self.assertIsNotNone(result["exclusion_reason"])

    def test_missing_bio_is_unknown(self):
        candidate = dict(self.candidate)
        candidate["bio"] = None

        result = evaluate(self.brand, candidate)

        self.assertIsNone(result["signals"]["scam_phrase"]["value"])


if __name__ == "__main__":
    unittest.main()