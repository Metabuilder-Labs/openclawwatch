"""Unit tests for drift detection pure functions."""
from ocw.core.drift import jaccard_similarity, z_score


class TestZScore:
    def test_standard_values(self):
        # value=12, mean=10, stddev=2 => z=1.0
        assert z_score(12.0, 10.0, 2.0) == 1.0

    def test_negative_z(self):
        assert z_score(8.0, 10.0, 2.0) == -1.0

    def test_zero_stddev_nonzero_deviation_returns_inf(self):
        assert z_score(100.0, 10.0, 0.0) == float("inf")

    def test_zero_stddev_zero_deviation_returns_zero(self):
        assert z_score(10.0, 10.0, 0.0) == 0.0

    def test_large_deviation(self):
        z = z_score(10000.0, 1000.0, 200.0)
        assert z == 45.0


class TestJaccardSimilarity:
    def test_identical_sets(self):
        assert jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        # intersection=1, union=3 => 1/3
        result = jaccard_similarity({"a", "b"}, {"b", "c"})
        assert abs(result - 1 / 3) < 0.001

    def test_both_empty(self):
        assert jaccard_similarity(set(), set()) == 1.0

    def test_one_empty(self):
        assert jaccard_similarity(set(), {"a"}) == 0.0

    def test_subset(self):
        # intersection=2, union=3 => 2/3
        result = jaccard_similarity({"a", "b"}, {"a", "b", "c"})
        assert abs(result - 2 / 3) < 0.001
