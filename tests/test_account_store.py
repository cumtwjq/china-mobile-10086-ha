"""Ensure account profiles and results stay separate during the upgrade."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "china_mobile_browser"))
import account_store  # noqa: E402


class AccountStoreTests(unittest.TestCase):
    def test_legacy_profile_and_new_accounts_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "old-profile"
            legacy.mkdir()
            new_profiles = root / "new-profiles"
            registry = root / "accounts.json"
            results = root / "results"
            account_a = "0123456789abcdef"
            account_b = "fedcba9876543210"
            with (
                patch.object(account_store, "LEGACY_PROFILE", legacy),
                patch.object(account_store, "PROFILES", new_profiles),
                patch.object(account_store, "REGISTRY", registry),
                patch.object(account_store, "RESULTS", results),
            ):
                self.assertEqual(account_store.load_accounts(), ["legacy"])
                account_store.register_account(account_a)
                account_store.register_account(account_b)
                self.assertEqual(
                    account_store.load_accounts(), ["legacy", account_a, account_b]
                )
                self.assertEqual(account_store.profile_path("legacy"), legacy)
                self.assertNotEqual(
                    account_store.profile_path(account_a),
                    account_store.profile_path(account_b),
                )
                self.assertNotEqual(
                    account_store.result_path(account_a),
                    account_store.result_path(account_b),
                )
                with self.assertRaises(ValueError):
                    account_store.profile_path("../another-account")
                account_store.profile_path(account_b).mkdir(parents=True)
                account_store.forget_account(account_b)
                self.assertEqual(account_store.load_accounts(), ["legacy", account_a])
                self.assertFalse(account_store.profile_path(account_b).exists())


if __name__ == "__main__":
    unittest.main()
