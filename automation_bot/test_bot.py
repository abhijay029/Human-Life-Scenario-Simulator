"""
Unit tests for the standalone automated simulator bot.
"""
from automation_bot.scenarios import SCENARIOS
from automation_bot.bot import render_gauge, trend_arrow


def test_scenarios_exist():
    assert "music" in SCENARIOS
    assert "startup" in SCENARIOS
    assert "medical" in SCENARIOS
    for key, sc in SCENARIOS.items():
        assert len(sc["personas"]) >= 2
        assert len(sc["playback_dialogue"]) >= 4
        assert sc["decision_point"]


def test_render_gauge():
    gauge_0 = render_gauge(0.0, 0.0, 100.0, width=10)
    assert "░" in gauge_0
    assert "█" not in gauge_0 or gauge_0.count("█") == 0

    gauge_100 = render_gauge(100.0, 0.0, 100.0, width=10)
    assert "█" in gauge_100
    assert "░" not in gauge_100

    gauge_50 = render_gauge(50.0, 0.0, 100.0, width=10)
    assert "█" in gauge_50
    assert "░" in gauge_50


def test_trend_arrow():
    up = trend_arrow("improving", "trust")
    assert "improving" in up
    down = trend_arrow("deteriorating", "trust")
    assert "worsening" in down

    # Tension inverted polarity
    tension_up = trend_arrow("improving", "tension")
    assert "improving" in tension_up
    tension_down = trend_arrow("deteriorating", "tension")
    assert "worsening" in tension_down
