import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch


class SetupNltkTests(unittest.TestCase):
    def module(self, missing=()):
        from scripts import setup_nltk
        installed = {path for paths in setup_nltk.RESOURCES.values() for path in paths}
        installed.difference_update(missing)
        def find(path):
            if path not in installed:
                raise LookupError(path)
            return path
        def download(name, **kwargs):
            installed.update(setup_nltk.RESOURCES[name])
            return True
        return setup_nltk, SimpleNamespace(
            data=SimpleNamespace(find=Mock(side_effect=find)),
            download=Mock(side_effect=download), __version__='3.10.3')

    def test_cached_resources_work_without_downloader_or_network(self):
        setup_nltk, nltk = self.module()
        nltk.download.side_effect = ValueError('SSRF attempt to restricted IP 198.18.0.100')
        with redirect_stdout(io.StringIO()):
            setup_nltk.prepare_resources(nltk)
        nltk.download.assert_not_called()

    def test_partial_cache_downloads_only_missing_resource_and_checks_result(self):
        setup_nltk, nltk = self.module([
            'taggers/averaged_perceptron_tagger_eng/averaged_perceptron_tagger_eng.weights.json'])
        with redirect_stdout(io.StringIO()):
            setup_nltk.prepare_resources(nltk)
        nltk.download.assert_called_once_with('averaged_perceptron_tagger_eng', raise_on_error=True)

    def test_g2p_archive_lookup_is_not_treated_as_optional(self):
        setup_nltk, nltk = self.module(['corpora/cmudict.zip'])
        with redirect_stdout(io.StringIO()):
            setup_nltk.prepare_resources(nltk)
        nltk.download.assert_called_once_with('cmudict', raise_on_error=True)

    def test_failed_or_incomplete_download_is_not_reported_ready(self):
        for result in (False, True):
            setup_nltk, nltk = self.module(['corpora/cmudict/cmudict'])
            nltk.download.side_effect = None
            nltk.download.return_value = result
            with self.subTest(result=result), redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                setup_nltk.prepare_resources(nltk)

    def test_blocked_dns_has_actionable_error_and_remains_failed(self):
        setup_nltk, nltk = self.module(['corpora/cmudict/cmudict'])
        nltk.download.side_effect = ValueError('Security Violation [pathsec.urlopen]: SSRF attempt to restricted IP 198.18.0.100')
        output = io.StringIO()
        with patch.dict('sys.modules', {'nltk': nltk}), redirect_stdout(output), redirect_stderr(output):
            self.assertEqual(setup_nltk.main(), 1)
        self.assertIn('198.18.0.100', output.getvalue())
        self.assertIn('raw.githubusercontent.com', output.getvalue())
        self.assertIn('NLTK_DATA', output.getvalue())
        self.assertIn('3.10.3', output.getvalue())


if __name__ == '__main__':
    unittest.main()
