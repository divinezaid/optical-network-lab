"""Constellation sanity: size, energy, Gray coding, noiseless round trip."""

import numpy as np
import pytest

from linkmodel import Format, constellation, demodulate, modulate

EXPECTED = {Format.QPSK: (4, 2), Format.QAM8: (8, 3), Format.QAM16: (16, 4)}


@pytest.mark.parametrize("fmt", list(Format))
def test_order_and_bits_per_symbol(fmt):
    c = constellation(fmt)
    assert (c.order, c.bits_per_symbol) == EXPECTED[fmt]


@pytest.mark.parametrize("fmt", list(Format))
def test_unit_average_energy(fmt):
    c = constellation(fmt)
    assert np.mean(np.abs(c.points) ** 2) == pytest.approx(1.0)


@pytest.mark.parametrize("fmt", list(Format))
def test_labels_are_unique(fmt):
    c = constellation(fmt)
    assert len({tuple(row) for row in c.labels}) == c.order


@pytest.mark.parametrize("fmt", list(Format))
def test_gray_coding_nearest_neighbours_differ_by_one_bit(fmt):
    """The most likely symbol error (to a nearest neighbour) costs one bit."""
    c = constellation(fmt)
    dist = np.abs(c.points[:, None] - c.points[None, :])
    d_min = np.min(dist[dist > 0])
    for i, j in zip(*np.where(np.isclose(dist, d_min))):
        assert np.sum(c.labels[i] != c.labels[j]) == 1


@pytest.mark.parametrize("fmt", list(Format))
def test_noiseless_round_trip(fmt):
    c = constellation(fmt)
    bits = np.random.default_rng(1).integers(0, 2, size=c.bits_per_symbol * 1000, dtype=np.int8)
    assert np.array_equal(demodulate(modulate(bits, c), c), bits)
