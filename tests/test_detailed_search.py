import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mcp'))
import server
from web_app import create_app, validated_advanced


class BuildDetailedQueryTests(unittest.TestCase):
    def test_operators_are_appended_in_stable_order(self):
        built = server.build_detailed_query(
            'recenzje gier',
            exclude=['używany'], include=['switch 2'], phrase='najlepsza gra',
            site=['metacritic.com'], not_site=['pinterest.com'],
        )
        self.assertEqual(
            built,
            'recenzje gier -"używany" +"switch 2" "najlepsza gra" site:metacritic.com -site:pinterest.com',
        )

    def test_user_quotes_are_stripped_so_operators_stay_inert(self):
        self.assertEqual(server.build_detailed_query('test', exclude=['a "b" c']), 'test -"a b c"')
        self.assertEqual(server.build_detailed_query('test', phrase='"cytat"'), 'test "cytat"')

    def test_empty_advanced_keeps_query_unchanged(self):
        self.assertEqual(server.build_detailed_query('test'), 'test')


class SanitizerTests(unittest.TestCase):
    def test_terms_are_trimmed_deduplicated_and_limited(self):
        self.assertEqual(server.sanitize_terms([' a ', 'a', 'b', 5, None]), ['a', 'b'])
        self.assertEqual(server.sanitize_terms([f't{i}' for i in range(20)]), [f't{i}' for i in range(10)])
        self.assertEqual(server.sanitize_terms('pojedynczy'), ['pojedynczy'])
        self.assertEqual(server.sanitize_terms(42), [])

    def test_hosts_accept_domains_and_reject_rubbish(self):
        self.assertEqual(server.sanitize_hosts(['wikipedia.org', 'https://gov.pl/web', 'a.pl']), ['wikipedia.org', 'gov.pl', 'a.pl'])
        self.assertEqual(server.sanitize_hosts(['*.example.org']), ['*.example.org'])
        self.assertEqual(server.sanitize_hosts(['złe;hosty', '', 'pl', 'a b.pl']), [])
        self.assertEqual(len(server.sanitize_hosts([f'h{i}.pl' for i in range(10)])), 5)


class WebSearchAdvancedTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_options_reject_before_any_provider_call(self):
        with patch.object(server, '_searxng') as primary, patch.object(server, '_perplexity') as fallback:
            for options in ({'time_range': 'hour'}, {'language': 'polski!'}, {'categories': ['nws']}):
                with self.subTest(options=options):
                    with self.assertRaises(ValueError):
                        await server.web_search('test', **options)
            primary.assert_not_called()
            fallback.assert_not_called()

    async def test_valid_options_build_query_and_reach_searxng(self):
        with patch.object(server, '_searxng', new_callable=AsyncMock) as primary, \
                patch.object(server, '_perplexity', new_callable=AsyncMock) as fallback:
            primary.return_value = [{'title': 't', 'url': 'https://example.org/', 'snippet': 's'}]
            result = json.loads(await server.web_search(
                'test', 5, time_range='week', language='pl', categories=['news'],
                exclude=['spam'], site=['gov.pl'],
            ))
            self.assertEqual(result['status'], 'ok')
            primary.assert_awaited_once_with('test -"spam" site:gov.pl', 5, time_range='week', language='pl', categories=['news'])
            fallback.assert_not_awaited()

    async def test_overlong_options_reject(self):
        with patch.object(server, '_searxng'), patch.object(server, '_perplexity'):
            with self.assertRaises(ValueError):
                await server.web_search('t' * 950, exclude=[f'słowo{i}' for i in range(10)])


class AdvancedValidationTests(unittest.TestCase):
    def test_none_returns_empty_dict(self):
        self.assertEqual(validated_advanced(None), {})

    def test_valid_payload_is_passed_through(self):
        cleaned = validated_advanced({'exclude': ['używany '], 'phrase': 'fraza', 'language': 'pl',
                                      'time_range': 'month', 'categories': ['news'], 'site': ['gov.pl']})
        self.assertEqual(cleaned['exclude'], ['używany'])
        self.assertEqual(cleaned['time_range'], 'month')
        self.assertEqual(cleaned['categories'], ['news'])

    def test_invalid_values_raise(self):
        for advanced in (
            {'time_range': 'hour'},
            {'categories': ['nws']},
            {'categories': ['general'] * 6},
            {'site': ['to nie host']},
            {'site': ['a' * 101]},
            {'exclude': ['x', 5]},
            {'phrase': 'x' * 201},
            {'language': 7},
            'lista',
        ):
            with self.subTest(advanced=advanced):
                with self.assertRaises(ValueError):
                    validated_advanced(advanced)


class SearchEndpointAdvancedTests(unittest.TestCase):
    def setUp(self):
        self.service = AsyncMock(return_value=json.dumps({
            "status": "ok", "source": "searxng",
            "results": [{"title": "t", "url": "https://example.org/", "snippet": "s"}], "errors": []}))
        self.client = TestClient(create_app(self.service, allowed_hosts=["testserver"]))

    def test_advanced_payload_reaches_service(self):
        response = self.client.post("/api/search", json={"query": "test", "max_results": 5, "advanced": {
            "exclude": ["używany"], "time_range": "week", "language": "pl", "categories": ["news"]}})
        self.assertEqual(response.status_code, 200)
        self.service.assert_called_once_with(
            "test", 5, exclude=["używany"], include=[], site=[], not_site=[], phrase="",
            language="pl", time_range="week", categories=["news"])

    def test_invalid_advanced_is_rejected_without_calling_the_service(self):
        response = self.client.post("/api/search", json={"query": "test", "advanced": {"time_range": "hour"}})
        self.assertEqual(response.status_code, 400)
        self.service.assert_not_called()


if __name__ == '__main__':
    unittest.main()
