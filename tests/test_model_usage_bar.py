"""Tests for ui/progress_bars.py ModelUsageBar — model family bucketing.

Regression tests for Fable/Claude 5 support: before the bucket refactor,
Fable tokens were counted in the total but never rendered as a segment or
named in the summary, silently deflating Sonnet/Opus percentages.
"""
import pytest

from ui.progress_bars import ModelUsageBar


def stats(input_tokens: int, output_tokens: int = 0) -> dict:
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


class TestModelUsageBar:
    def test_fable_only_shows_fable_100pct(self):
        bar = ModelUsageBar()
        result = bar.render({"claude-fable-5": stats(1000)})
        assert "Fable 100.0%" in result

    def test_mythos_counts_as_fable(self):
        bar = ModelUsageBar()
        result = bar.render({"claude-mythos-5": stats(1000)})
        assert "Fable 100.0%" in result

    def test_fable_mixed_with_sonnet_and_opus(self):
        bar = ModelUsageBar()
        result = bar.render({
            "claude-sonnet-5": stats(500),
            "claude-opus-4-8": stats(250),
            "claude-fable-5": stats(250),
        })
        assert "Sonnet 50.0%" in result
        assert "Opus 25.0%" in result
        assert "Fable 25.0%" in result

    def test_unknown_model_shows_other(self):
        bar = ModelUsageBar()
        result = bar.render({"some-future-model": stats(1000)})
        assert "Other 100.0%" in result

    def test_sonnet_opus_summary_unchanged(self):
        bar = ModelUsageBar()
        result = bar.render({
            "claude-sonnet-5": stats(600),
            "claude-opus-4-8": stats(400),
        })
        assert "Sonnet 60.0%" in result
        assert "Opus 40.0%" in result

    def test_segment_widths_fill_bar_exactly(self):
        bar = ModelUsageBar(width=10)
        result = bar.render({
            "claude-sonnet-5": stats(333),
            "claude-opus-4-8": stats(333),
            "claude-fable-5": stats(334),
        })
        assert result.count("█") == 10

    def test_zero_tokens_renders_empty_message(self):
        bar = ModelUsageBar()
        result = bar.render({"claude-fable-5": stats(0)})
        assert "No tokens used" in result

    def test_empty_stats_renders_no_model_data(self):
        bar = ModelUsageBar()
        result = bar.render({})
        assert "No model data" in result
