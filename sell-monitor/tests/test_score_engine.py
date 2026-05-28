from __future__ import annotations

import unittest

from sell_monitor.domain.models import Signal
from sell_monitor.scoring.score_engine import compute_score


class ScoreEngineTest(unittest.TestCase):
    def test_sums_triggered_scores(self) -> None:
        signals = [
            Signal("a", 1, True, "a"),
            Signal("b", 2, False, "b"),
            Signal("c", 3, True, "c"),
        ]
        self.assertEqual(compute_score(signals), 4)


if __name__ == "__main__":
    unittest.main()

