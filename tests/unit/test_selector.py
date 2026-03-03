"""Unit tests for sigmoid refinement algorithm and PromptSelector."""

import math
import uuid
from unittest.mock import MagicMock, patch

import pytest
from simpa.db.models import RefinedPrompt
from simpa.prompts.selector import EXAMPLE_PROBABILITIES, PromptSelector


class TestSigmoidBoundaryConditions:
    """Test sigmoid probability calculations at score boundaries."""

    def test_sigmoid_score_1_0(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 1.0 (~95.3%)."""
        probability = prompt_selector.calculate_refinement_probability(1.0)
        expected = 0.953
        assert probability == pytest.approx(expected, abs=0.01)

    def test_sigmoid_score_1_5(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 1.5 (~90.5%)."""
        probability = prompt_selector.calculate_refinement_probability(1.5)
        expected = 0.905
        assert probability == pytest.approx(expected, abs=0.01)

    def test_sigmoid_score_2_0(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 2.0 (~81.8%)."""
        probability = prompt_selector.calculate_refinement_probability(2.0)
        expected = 0.818
        assert probability == pytest.approx(expected, abs=0.01)

    def test_sigmoid_score_2_5(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 2.5 (~67.9%)."""
        probability = prompt_selector.calculate_refinement_probability(2.5)
        expected = 0.679
        assert probability == pytest.approx(expected, abs=0.01)

    def test_sigmoid_score_3_0(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 3.0 (50% - coin flip)."""
        probability = prompt_selector.calculate_refinement_probability(3.0)
        # At mu=3.0, should be exactly 0.5
        assert probability == pytest.approx(0.5, abs=0.001)

    def test_sigmoid_score_3_5(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 3.5 (~32.1%)."""
        probability = prompt_selector.calculate_refinement_probability(3.5)
        expected = 0.321
        assert probability == pytest.approx(expected, abs=0.01)

    def test_sigmoid_score_4_0(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 4.0 (~18.2%)."""
        probability = prompt_selector.calculate_refinement_probability(4.0)
        expected = 0.182
        assert probability == pytest.approx(expected, abs=0.01)

    def test_sigmoid_score_4_5(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 4.5 (~9.5%)."""
        probability = prompt_selector.calculate_refinement_probability(4.5)
        expected = 0.095
        assert probability == pytest.approx(expected, abs=0.01)

    def test_sigmoid_score_5_0(self, prompt_selector: PromptSelector):
        """Test refinement probability at score 5.0 (~4.7%)."""
        probability = prompt_selector.calculate_refinement_probability(5.0)
        expected = 0.047
        assert probability == pytest.approx(expected, abs=0.01)

    def test_all_score_bins_match_documentation(self, prompt_selector: PromptSelector):
        """Verify all score bins match documented EXAMPLE_PROBABILITIES."""
        for score, expected in EXAMPLE_PROBABILITIES.items():
            actual = prompt_selector.calculate_refinement_probability(score)
            assert actual == pytest.approx(expected, abs=0.01), f"Score {score} mismatch"


class TestSigmoidParameterVariation:
    """Test sigmoid behavior with different parameter values."""

    def test_steepness_k_variation(self):
        """Test that higher k values create steeper curves."""
        selector = PromptSelector()
        selector.mu = 3.0
        selector.min_probability = 0.0  # Disable floor for this test
        
        # Test different k values
        k_values = [0.5, 1.0, 1.5, 2.0, 2.5]
        results = {}
        
        for k in k_values:
            selector.k = k
            prob = selector.calculate_refinement_probability(2.0)
            results[k] = prob
        
        # Higher k should result in higher probability at score 2.0 (steeper drop)
        assert results[0.5] < results[2.5]

    def test_midpoint_mu_variation(self):
        """Test that mu shifts the 50% probability point."""
        selector = PromptSelector()
        selector.k = 1.5
        selector.min_probability = 0.0
        
        # Test that probability is ~50% at each mu value
        for mu in [2.0, 2.5, 3.0, 3.5, 4.0]:
            selector.mu = mu
            prob = selector.calculate_refinement_probability(mu)
            assert prob == pytest.approx(0.5, abs=0.001)


class TestExplorationFloor:
    """Test minimum refinement probability (exploration floor)."""

    def test_exploration_floor_enforced_at_high_score(self, prompt_selector: PromptSelector):
        """Test that score 5.0 respects minimum probability floor."""
        probability = prompt_selector.calculate_refinement_probability(5.0)
        
        # The raw sigmoid gives ~0.047, but floor should enforce 0.05
        assert probability >= 0.05
        assert probability == pytest.approx(0.05, abs=0.01)

    def test_exploration_floor_not_applied_at_low_score(self, prompt_selector: PromptSelector):
        """Test that low scores use raw sigmoid value."""
        probability = prompt_selector.calculate_refinement_probability(2.0)
        
        # Raw sigmoid for 2.0 is ~0.818, which is above floor
        assert probability == pytest.approx(0.818, abs=0.01)

    def test_custom_floor_value(self):
        """Test custom minimum probability values."""
        selector = PromptSelector()
        selector.min_probability = 0.10
        
        # At score 4.5, raw sigmoid is ~0.095, which is below new floor
        probability = selector.calculate_refinement_probability(4.5)
        assert probability >= 0.10


class TestDecayFormula:
    """Test usage decay formula blending."""

    def test_decay_formula_values(self):
        """Test the usage decay formula p_final = 0.8*p_refine + 0.2*e^(-usage/30)."""
        import math
        
        def calculate_decay(p_refine: float, usage: int) -> float:
            return 0.8 * p_refine + 0.2 * math.exp(-usage / 30)
        
        # Test with p_refine = 0.5 (score 3.0)
        # At usage 0: p_final = 0.8*0.5 + 0.2*1.0 = 0.4 + 0.2 = 0.6
        assert calculate_decay(0.5, 0) == pytest.approx(0.6, abs=0.01)
        
        # At usage 10: p_final ≈ 0.8*0.5 + 0.2*0.717 = 0.4 + 0.143 = 0.543
        assert calculate_decay(0.5, 10) == pytest.approx(0.543, abs=0.01)
        
        # At usage 30: p_final ≈ 0.8*0.5 + 0.2*0.368 = 0.4 + 0.074 = 0.474
        assert calculate_decay(0.5, 30) == pytest.approx(0.474, abs=0.01)
        
        # At usage 100: p_final ≈ 0.8*0.5 + 0.2*0.036 = 0.4 + 0.007 = 0.407
        assert calculate_decay(0.5, 100) == pytest.approx(0.407, abs=0.01)


class TestDecisionLogic:
    """Test prompt refinement decision logic."""

    def test_no_existing_prompt_creates_new(self, prompt_selector: PromptSelector):
        """Test that None prompt results in new prompt creation."""
        result = prompt_selector.should_create_new_prompt(None)
        assert result is True

    def test_high_score_prompt_reuse(self, prompt_selector: PromptSelector):
        """Test that high-score prompts are reused (random > probability)."""
        # Create mock prompt with high score
        prompt = MagicMock(spec=RefinedPrompt)
        prompt.id = uuid.uuid4()
        prompt.average_score = 4.5  # Low probability (~9.5%)
        prompt.usage_count = 10
        
        # Mock random to return value above probability threshold
        with patch("simpa.prompts.selector.random.random", return_value=0.5):
            result = prompt_selector.should_create_new_prompt(prompt)
            assert result is False  # Should reuse (no new prompt)

    def test_low_score_prompt_refine(self, prompt_selector: PromptSelector):
        """Test that low-score prompts trigger refinement."""
        # Create mock prompt with low score
        prompt = MagicMock(spec=RefinedPrompt)
        prompt.id = uuid.uuid4()
        prompt.average_score = 2.0  # High probability (~82%)
        prompt.usage_count = 5
        
        # Mock random to return value below probability threshold
        with patch("simpa.prompts.selector.random.random", return_value=0.5):
            result = prompt_selector.should_create_new_prompt(prompt)
            assert result is True  # Should create new/refined prompt

    def test_neutral_score_random_boundary(self, prompt_selector: PromptSelector):
        """Test 50/50 decision at neutral score."""
        prompt = MagicMock(spec=RefinedPrompt)
        prompt.id = uuid.uuid4()
        prompt.average_score = 3.0  # Exactly 50%
        prompt.usage_count = 5
        
        # Test with random just below threshold
        with patch("simpa.prompts.selector.random.random", return_value=0.4):
            result = prompt_selector.should_create_new_prompt(prompt)
            assert result is True  # 0.4 < 0.5, so refine
        
        # Test with random just above threshold
        with patch("simpa.prompts.selector.random.random", return_value=0.6):
            result = prompt_selector.should_create_new_prompt(prompt)
            assert result is False  # 0.6 > 0.5, so reuse

    def test_unused_prompt_defaults_to_neutral(self, prompt_selector: PromptSelector):
        """Test that prompts with no usage default to neutral score (2.5)."""
        prompt = MagicMock(spec=RefinedPrompt)
        prompt.id = uuid.uuid4()
        prompt.average_score = 4.5  # This should be ignored
        prompt.usage_count = 0  # Forces default score of 2.5
        
        # Calculate expected probability for score 2.5 (~67.9%)
        # With random = 0.6, should trigger refinement (0.6 < 0.679)
        with patch("simpa.prompts.selector.random.random", return_value=0.6):
            result = prompt_selector.should_create_new_prompt(prompt)
            assert result is True


class TestSelectBestPrompt:
    """Test best prompt selection from candidates."""

    def test_empty_list_returns_none(self, prompt_selector: PromptSelector):
        """Test that empty prompt list returns None."""
        result = prompt_selector.select_best_prompt([])
        assert result is None

    def test_selects_highest_scoring_prompt(self, prompt_selector: PromptSelector):
        """Test selecting prompt with highest average score."""
        prompts = [
            MagicMock(spec=RefinedPrompt, average_score=3.0, usage_count=5),
            MagicMock(spec=RefinedPrompt, average_score=4.5, usage_count=10),  # Best
            MagicMock(spec=RefinedPrompt, average_score=2.0, usage_count=3),
        ]
        
        result = prompt_selector.select_best_prompt(prompts)
        assert result.average_score == 4.5

    def test_prefer_prompts_with_usage(self, prompt_selector: PromptSelector):
        """Test that prompts with usage history are preferred over new ones."""
        prompts = [
            MagicMock(spec=RefinedPrompt, average_score=1.0, usage_count=1),  # Has usage
            MagicMock(spec=RefinedPrompt, average_score=5.0, usage_count=0),  # No usage
        ]
        
        result = prompt_selector.select_best_prompt(prompts)
        # Should select the one with usage, despite lower score
        assert result.usage_count > 0

    def test_falls_back_to_vector_similarity(self, prompt_selector: PromptSelector):
        """Test fallback to vector similarity when no usage history."""
        prompts = [
            MagicMock(spec=RefinedPrompt, average_score=0.0, usage_count=0),
            MagicMock(spec=RefinedPrompt, average_score=0.0, usage_count=0),
        ]
        
        result = prompt_selector.select_best_prompt(prompts)
        # Should return first one (assumed highest similarity from search)
        assert result is prompts[0]

    def test_tiebreaker_by_usage_count(self, prompt_selector: PromptSelector):
        """Test that usage count breaks score ties."""
        prompts = [
            MagicMock(spec=RefinedPrompt, average_score=4.0, usage_count=5),
            MagicMock(spec=RefinedPrompt, average_score=4.0, usage_count=15),  # More usage
        ]
        
        result = prompt_selector.select_best_prompt(prompts)
        assert result.usage_count == 15


class TestSigmoidMonotonicity:
    """Test that sigmoid behaves correctly mathematically."""

    def test_probability_decreases_with_score(self, prompt_selector: PromptSelector):
        """Test that refinement probability decreases monotonically with score."""
        scores = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
        probabilities = [
            prompt_selector.calculate_refinement_probability(s) 
            for s in scores
        ]
        
        # Each probability should be less than or equal to the previous
        for i in range(1, len(probabilities)):
            assert probabilities[i] <= probabilities[i-1]

    def test_probability_within_valid_range(self, prompt_selector: PromptSelector):
        """Test that all probabilities are within [0, 1]."""
        for score in [1.0, 2.0, 3.0, 4.0, 5.0]:
            prob = prompt_selector.calculate_refinement_probability(score)
            assert 0.0 <= prob <= 1.0
