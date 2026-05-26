import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from civitai_checker import CivitaiChecker


class CheckerTestCase(unittest.TestCase):
    def create_checker(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        config_path = os.path.join(temp_dir.name, "config.json")
        with open(config_path, "w", encoding="utf-8") as file:
            json.dump({"models": [], "check_interval_hours": 24}, file)

        return CivitaiChecker(config_file=config_path)


class CivitaiCheckerSiteSupportTests(CheckerTestCase):
    def test_extract_model_reference_supports_civitai_red(self):
        checker = self.create_checker()

        reference = checker.extract_model_reference(
            "https://civitai.red/models/4384/dreamshaper"
        )

        self.assertEqual(
            reference,
            {"site": "civitai.red", "model_id": "4384"},
        )

    def test_get_api_base_url_defaults_old_models_to_civitai_com(self):
        checker = self.create_checker()

        api_base_url = checker.get_api_base_url({"id": "4384"})

        self.assertEqual(api_base_url, "https://civitai.com/api/v1")

    def test_get_api_base_url_uses_model_site_when_present(self):
        checker = self.create_checker()

        api_base_url = checker.get_api_base_url(
            {"id": "4384", "site": "civitai.red"}
        )

        self.assertEqual(api_base_url, "https://civitai.red/api/v1")

    def test_extract_model_reference_rejects_unsupported_site(self):
        checker = self.create_checker()

        reference = checker.extract_model_reference(
            "https://example.com/models/4384/dreamshaper"
        )

        self.assertIsNone(reference)


class CivitaiCheckerDataDirTests(unittest.TestCase):
    def test_uses_environment_data_dir_for_config_and_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(config_path, "w", encoding="utf-8") as file:
                json.dump({"models": [], "check_interval_hours": 24}, file)

            original_data_dir = os.environ.get("CIVITAI_CHECKER_DATA_DIR")
            try:
                os.environ["CIVITAI_CHECKER_DATA_DIR"] = temp_dir

                checker = CivitaiChecker()

                self.assertEqual(checker.config_file, config_path)
                self.assertEqual(
                    checker.history_file,
                    os.path.join(temp_dir, "model_history.json"),
                )
            finally:
                if original_data_dir is None:
                    os.environ.pop("CIVITAI_CHECKER_DATA_DIR", None)
                else:
                    os.environ["CIVITAI_CHECKER_DATA_DIR"] = original_data_dir


class CivitaiCheckerUpdateFlowTests(CheckerTestCase):
    def test_check_model_updates_uses_model_site_for_version_lookup(self):
        checker = self.create_checker()
        checker.get_model_versions = MagicMock(
            return_value=[{"id": "version-1", "name": "v1", "createdAt": "2026-05-26T00:00:00"}]
        )
        checker.load_history = MagicMock(return_value={})
        checker.save_history = MagicMock()

        checker.check_model_updates(
            {
                "id": "4384",
                "site": "civitai.red",
                "alias": "DreamShaper",
                "url": "https://civitai.red/models/4384/dreamshaper",
            }
        )

        checker.get_model_versions.assert_called_once_with("4384", site="civitai.red")

    def test_remove_model_supports_full_url_for_specific_site(self):
        checker = self.create_checker()
        checker.config["models"] = [
            {
                "id": "4384",
                "site": "civitai.com",
                "alias": "DreamShaper Com",
                "url": "https://civitai.com/models/4384/dreamshaper",
            },
            {
                "id": "4384",
                "site": "civitai.red",
                "alias": "DreamShaper Red",
                "url": "https://civitai.red/models/4384/dreamshaper",
            },
        ]
        checker.save_config = MagicMock()

        removed = checker.remove_model("https://civitai.red/models/4384/dreamshaper")

        self.assertTrue(removed)
        self.assertEqual(len(checker.config["models"]), 1)
        self.assertEqual(checker.config["models"][0]["site"], "civitai.com")


if __name__ == "__main__":
    unittest.main()