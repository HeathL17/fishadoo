"""Tests for shared/string_generator.py."""

import pytest

from shared.string_generator import CHARSETS, generate_random_string


class TestGenerateRandomString:
    """Tests for generate_random_string."""

    # ------------------------------------------------------------------
    # Basic correctness
    # ------------------------------------------------------------------

    def test_returns_string_of_correct_length(self) -> None:
        result = generate_random_string(length=16)
        assert len(result) == 16

    def test_all_characters_in_charset(self) -> None:
        result = generate_random_string(length=200, charset="alphanumeric")
        valid_chars = set(CHARSETS["alphanumeric"])
        assert all(c in valid_chars for c in result)

    def test_all_charsets_produce_correct_output(self) -> None:
        for name, chars in CHARSETS.items():
            result = generate_random_string(length=50, charset=name)
            assert len(result) == 50, f"Wrong length for charset {name!r}"
            assert all(c in chars for c in result), f"Bad char in charset {name!r}"

    # ------------------------------------------------------------------
    # Seeded (deterministic) generation
    # ------------------------------------------------------------------

    def test_seeded_generation_is_deterministic(self) -> None:
        r1 = generate_random_string(length=32, seed_override="test-seed")
        r2 = generate_random_string(length=32, seed_override="test-seed")
        assert r1 == r2

    def test_different_seeds_produce_different_strings(self) -> None:
        r1 = generate_random_string(length=32, seed_override="seed-A")
        r2 = generate_random_string(length=32, seed_override="seed-B")
        assert r1 != r2

    def test_no_seed_produces_different_strings(self) -> None:
        """Without a seed, two calls should (overwhelmingly) differ."""
        results = {generate_random_string(length=32) for _ in range(10)}
        # With 32 alphanumeric chars the probability of a collision is negligible.
        assert len(results) == 10

    # ------------------------------------------------------------------
    # Edge cases / validation
    # ------------------------------------------------------------------

    def test_raises_on_zero_length(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            generate_random_string(length=0)

    def test_raises_on_negative_length(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            generate_random_string(length=-1)

    def test_raises_on_unknown_charset(self) -> None:
        with pytest.raises(ValueError, match="Unknown charset"):
            generate_random_string(length=10, charset="klingon")

    def test_length_one(self) -> None:
        result = generate_random_string(length=1)
        assert len(result) == 1

    def test_large_length(self) -> None:
        result = generate_random_string(length=10_000)
        assert len(result) == 10_000
