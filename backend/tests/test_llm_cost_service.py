"""Tests for LLM cost estimation service."""

import unittest

from app.services.llm_cost_service import estimate_llm_cost


class LlmCostServiceTests(unittest.TestCase):
    """Test cases for LLM cost estimation."""

    def test_known_provider_model_returns_non_zero_estimate(self) -> None:
        """Estimate cost for known provider and model returns positive value."""
        cost = estimate_llm_cost(
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        self.assertGreater(cost, 0.0)

    def test_openai_gpt4o_mini_returns_correct_estimate(self) -> None:
        """Estimate cost for GPT-4o-mini matches expected calculation."""
        cost = estimate_llm_cost(
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        expected = 0.00015 + 0.0006
        self.assertAlmostEqual(cost, expected, places=6)

    def test_deepseek_v4_flash_returns_correct_estimate(self) -> None:
        """Estimate cost for deepseek-v4-flash matches expected calculation."""
        cost = estimate_llm_cost(
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        expected = 0.00002 + 0.00006
        self.assertAlmostEqual(cost, expected, places=6)

    def test_unknown_provider_returns_zero(self) -> None:
        """Unknown provider returns 0.0 cost estimate."""
        cost = estimate_llm_cost(
            provider="unknown_provider",
            model="some-model",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        self.assertEqual(cost, 0.0)

    def test_unknown_model_returns_zero(self) -> None:
        """Unknown model for known provider returns 0.0 cost estimate."""
        cost = estimate_llm_cost(
            provider="openai",
            model="unknown-model",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        self.assertEqual(cost, 0.0)

    def test_zero_tokens_returns_zero(self) -> None:
        """Zero tokens returns 0.0 cost estimate."""
        cost = estimate_llm_cost(
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_tokens=0,
            completion_tokens=0,
        )
        self.assertEqual(cost, 0.0)

    def test_zero_prompt_tokens_returns_only_completion_cost(self) -> None:
        """Zero prompt tokens returns only completion cost."""
        cost = estimate_llm_cost(
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_tokens=0,
            completion_tokens=1000,
        )
        expected = 0.00006
        self.assertAlmostEqual(cost, expected, places=6)

    def test_zero_completion_tokens_returns_only_prompt_cost(self) -> None:
        """Zero completion tokens returns only prompt cost."""
        cost = estimate_llm_cost(
            provider="deepseek",
            model="deepseek-v4-flash",
            prompt_tokens=1000,
            completion_tokens=0,
        )
        expected = 0.00002
        self.assertAlmostEqual(cost, expected, places=6)

    def test_realistic_token_counts_returns_sensible_estimate(self) -> None:
        """Realistic token counts return a sensible cost estimate."""
        cost = estimate_llm_cost(
            provider="openai",
            model="gpt-4o-mini",
            prompt_tokens=500,
            completion_tokens=125,
        )
        self.assertGreater(cost, 0.0)
        self.assertLess(cost, 1.0)

    def test_gpt4_turbo_returns_higher_cost(self) -> None:
        """GPT-4 Turbo returns higher cost than smaller models."""
        gpt4_cost = estimate_llm_cost(
            provider="openai",
            model="gpt-4-turbo",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        gpt35_cost = estimate_llm_cost(
            provider="openai",
            model="gpt-3.5-turbo",
            prompt_tokens=1000,
            completion_tokens=1000,
        )
        self.assertGreater(gpt4_cost, gpt35_cost)


if __name__ == "__main__":
    unittest.main()