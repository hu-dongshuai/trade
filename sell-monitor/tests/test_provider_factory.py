from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path

from sell_monitor.config import load_default_config
from sell_monitor.data.akshare_provider import AkshareMarketDataProvider
from sell_monitor.data.fallback_provider import CachedFallbackMarketDataProvider
from sell_monitor.data.market_data_provider import StaticMarketDataProvider
from sell_monitor.data.provider_factory import build_market_data_provider


class ProviderFactoryTest(unittest.TestCase):
    def test_builds_static_provider_by_default(self) -> None:
        old_provider = os.environ.pop("SELL_MONITOR_PROVIDER", None)
        old_userdata = os.environ.pop("SELL_MONITOR_MINIQMT_USERDATA_PATH", None)
        old_env_file = os.environ.get("SELL_MONITOR_ENV_FILE")
        os.environ["SELL_MONITOR_ENV_FILE"] = str(Path(__file__).resolve().parent / "missing.env")
        try:
            config = load_default_config(Path(__file__).resolve().parents[1])
            provider = build_market_data_provider(config)
            self.assertIsInstance(provider, StaticMarketDataProvider)
        finally:
            if old_provider is not None:
                os.environ["SELL_MONITOR_PROVIDER"] = old_provider
            if old_userdata is not None:
                os.environ["SELL_MONITOR_MINIQMT_USERDATA_PATH"] = old_userdata
            if old_env_file is None:
                os.environ.pop("SELL_MONITOR_ENV_FILE", None)
            else:
                os.environ["SELL_MONITOR_ENV_FILE"] = old_env_file

    def test_builds_akshare_provider_when_selected(self) -> None:
        old_provider = os.environ.get("SELL_MONITOR_PROVIDER")
        old_env_file = os.environ.get("SELL_MONITOR_ENV_FILE")
        fake_module = types.SimpleNamespace()
        sys.modules["akshare"] = fake_module
        os.environ["SELL_MONITOR_PROVIDER"] = "akshare"
        os.environ["SELL_MONITOR_ENV_FILE"] = str(Path(__file__).resolve().parent / "missing.env")
        try:
            config = load_default_config(Path(__file__).resolve().parents[1])
            provider = build_market_data_provider(config)
            self.assertIsInstance(provider, CachedFallbackMarketDataProvider)
            self.assertIsInstance(provider.primary_provider, AkshareMarketDataProvider)
        finally:
            if old_provider is None:
                os.environ.pop("SELL_MONITOR_PROVIDER", None)
            else:
                os.environ["SELL_MONITOR_PROVIDER"] = old_provider
            sys.modules.pop("akshare", None)
            if old_env_file is None:
                os.environ.pop("SELL_MONITOR_ENV_FILE", None)
            else:
                os.environ["SELL_MONITOR_ENV_FILE"] = old_env_file
