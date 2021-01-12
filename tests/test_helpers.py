import numpy as np
import pytest

from maurice.helpers import compare_smart_bins, is_continuous, is_discrete, smart_bins
from maurice.types import ArrayLike


@pytest.mark.parametrize(
    "data,expected", (([1, 2, 3, 4], True), ([1.0, 2.0, 3.0, 4.0], True), ([1.2, 2, 3, 4], False))
)
def test_is_discrete(data, expected) -> None:
    assert is_discrete(data) is expected


@pytest.mark.parametrize(
    "data,expected", (([1, 2, 3, 4], False), ([1.0, 2.0, 3.0, 4.0], False), ([1.2, 2, 3, 4], True))
)
def test_is_continuous(data, expected) -> None:
    assert is_continuous(data) is expected


data = [
    np.random.normal(loc=0.0, scale=1.0, size=1200),
    np.random.laplace(loc=0.0, scale=1, size=1000),
    np.random.lognormal(mean=1.0, sigma=0.8, size=1200),
    np.random.poisson(lam=10, size=300),
]


@pytest.mark.parametrize(
    "data,method,expected_return",
    (
        (data[2], "sqrt", 19),
        (data[2], "rice", 19),
        (data[2], "doane", 19),
        (data[2], "scott", 19),
        (data[2], "freedman–diaconis", 19),
    ),
)
def test_smart_bins(data: ArrayLike, method: str, expected_return) -> None:
    bins = smart_bins(data=data, method=method)
    assert isinstance(bins, int)
    assert bins <= np.unique(data).size
    if is_discrete(data):
        assert bins <= np.max(data) - np.min(data)


@pytest.mark.parametrize("i,data", (*enumerate(data),))
def test_compare_smart_bins(i: int, data: ArrayLike) -> None:
    fig = compare_smart_bins(data=data)
    # fig.savefig(f"./tests/test_compare_smart_bins_{i}.png")
