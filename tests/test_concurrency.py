import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mcp'))
import server


class ConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_delayed_searches_overlap_and_event_loop_stays_responsive(self):
        entered = 0
        both_entered = asyncio.Event()

        async def delayed(query, count):
            nonlocal entered
            entered += 1
            if entered == 2:
                both_entered.set()
            await asyncio.sleep(1)
            return [{'title': query, 'url': 'https://example.org', 'snippet': ''}]

        with patch.object(server, '_searxng', side_effect=delayed), patch.object(server, '_perplexity', new_callable=AsyncMock) as paid:
            started = time.perf_counter()
            tasks = [asyncio.create_task(server.web_search(q)) for q in ['one', 'two']]
            await asyncio.wait_for(both_entered.wait(), timeout=0.5)
            replies = await asyncio.gather(*tasks)
            self.assertLess(time.perf_counter() - started, 1.5)
            self.assertEqual([json.loads(r)['source'] for r in replies], ['searxng', 'searxng'])
            paid.assert_not_called()

    async def test_one_hundred_paid_attempts_allow_exactly_fifty_http_requests(self):
        response = Mock()
        response.json.return_value = {'results': []}

        async def paid_response(*args, **kwargs):
            await asyncio.sleep(0.01)
            return response

        client = AsyncMock()
        client.post.side_effect = paid_response
        state = {'day': server.datetime.date.today().isoformat(), 'count': 0}
        with patch.object(server, 'PPLX_KEY', 'fixture-only'), patch.object(server, 'PPLX_DAILY_LIMIT', 50), patch.object(server, '_pplx', state), patch.object(server, 'get_http_client', return_value=client):
            replies = await asyncio.gather(*(server._perplexity('test', 1) for _ in range(100)), return_exceptions=True)
        self.assertEqual(client.post.await_count, 50)
        self.assertEqual(sum(isinstance(r, RuntimeError) for r in replies), 50)
        self.assertEqual(state['count'], 50)

    async def test_cancelled_paid_request_does_not_refund_unknown_cost(self):
        entered = asyncio.Event()

        async def waiting(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()

        client = AsyncMock()
        client.post.side_effect = waiting
        state = {'day': server.datetime.date.today().isoformat(), 'count': 0}
        with patch.object(server, 'PPLX_KEY', 'fixture-only'), patch.object(server, '_pplx', state), patch.object(server, 'get_http_client', return_value=client):
            task = asyncio.create_task(server._perplexity('test', 1))
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(state['count'], 1)

    async def test_shared_http_client_is_reused_and_closed(self):
        await server.close_http_client()
        first = server.get_http_client()
        second = server.get_http_client()
        self.assertIs(first, second)
        self.assertFalse(first.is_closed)
        await server.close_http_client()
        self.assertTrue(first.is_closed)

    async def test_http_client_is_pinned_to_ipv4(self):
        await server.close_http_client()
        client = server.get_http_client()
        self.addCleanup(server.close_http_client)
        self.assertEqual(client._transport._pool._local_address, "0.0.0.0")
