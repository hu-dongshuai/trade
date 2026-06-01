from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime

from sell_monitor.data.baostock_provider import BaostockMarketDataProvider


class _FakeLoginResult:
    error_code = "0"
    error_msg = ""


class _FakeResultSet:
    error_code = "0"
    error_msg = ""
    fields = ["date", "time", "code", "open", "high", "low", "close", "volume"]

    def __init__(self) -> None:
        self.rows = [
            ["2026-05-27", "20260527094500000", "sz.002241", "10", "11", "9", "10.5", "1000"],
            ["2026-05-27", "20260527100000000", "sz.002241", "10.5", "11.2", "10.2", "11", "1200"],
        ]
        self.idx = -1

    def next(self) -> bool:
        self.idx += 1
        return self.idx < len(self.rows)

    def get_row_data(self):
        return self.rows[self.idx]


class BaostockProviderTest(unittest.TestCase):
    def test_reads_m15_bars_from_baostock_result_set(self) -> None:
        fake_bs = types.SimpleNamespace(
            login=lambda: _FakeLoginResult(),
            logout=lambda: None,
            query_history_k_data_plus=lambda *args, **kwargs: _FakeResultSet(),
        )
        old_module = sys.modules.get("baostock")
        sys.modules["baostock"] = fake_bs
        try:
            provider = BaostockMarketDataProvider()
            bars = provider.get_m15_bars("002241", limit=2)
        finally:
            if old_module is None:
                sys.modules.pop("baostock", None)
            else:
                sys.modules["baostock"] = old_module

        self.assertEqual(2, len(bars))
        self.assertEqual(datetime(2026, 5, 27, 10, 0), bars[-1].ts)
        self.assertEqual(11.0, bars[-1].close)


if __name__ == "__main__":
    unittest.main()
