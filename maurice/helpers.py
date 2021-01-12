import math

import numpy as np
from matplotlib.figure import Figure
from scipy.stats import skew

from maurice.types import ArrayLike


def is_discrete(data: ArrayLike) -> bool:
    """Check if a sequence of numbers appears to be discrete.

    Returns `True` for the trivial case where the array is integer valued. Otherwise, if a `float`-values array is
    passed, this function returns `True` if and only if all elements do not contain a fractional part.
    """
    data = np.asarray(data)
    return np.all(np.mod(data, 1) == 0)


def is_continuous(data: ArrayLike) -> bool:
    return not is_discrete(data=data)


SMART_BIN_METHODS = ["sqrt", "sturges", "rice", "doane", "scott", "freedman–diaconis"]


def smart_bins(data: ArrayLike, method: str = "freedman–diaconis") -> int:
    """Get the "ideal" number of histogram bins for a given dataset.

    method: Literal["sqrt", "sturges", "rice", "doane", "scott", "freedman–diaconis"]

    Read more about the different methods at <https://en.wikipedia.org/wiki/Histogram#Number_of_bins_and_width>.

    Note implemented:
        - Minimizing cross-validation estimated squared error
        - Shimazaki and Shinomoto's choice

    """
    data = np.asarray(data)
    n_observations = data.size
    data_range = np.max(data) - np.min(data)

    def get_nbins(bin_width: float) -> int:
        # The number of bins can be calculated from a given bin-width
        return math.ceil(data_range / bin_width)

    # These first 4 method calculate the number of bins
    # directly (bypassing calculating the bin-width first)
    if method == "sqrt":
        n_bins = math.ceil(math.sqrt(n_observations))
    elif method == "sturges":
        n_bins = 1 + math.ceil(math.log2(n_observations))
    elif method == "rice":
        n_bins = math.ceil(2 * n_observations ** (1 / 3.0))
    elif method == "doane":
        s = math.sqrt((6 * (n_observations - 2)) / ((n_observations + 1) * (n_observations + 3)))
        n_bins = 1 + math.ceil(math.log2(n_observations) + math.log2(1 + abs(skew(data)) / s))

    # These last 2 methods calculate the bin-width first, which is then
    # used to calculate the number of bins (see get_nbins)
    elif method == "scott":
        n_bins = get_nbins(bin_width=3.49 * np.std(data) / (n_observations ** (1 / 3.0)))
    elif method == "freedman–diaconis":
        iqr = np.subtract(*np.percentile(data, [75, 25]))
        n_bins = get_nbins(bin_width=2 * iqr / (n_observations ** (1 / 3.0)))

    # TODO: There are much better ways to deal with this
    #       (e.g.: Enums, dicts, or a custom object...)
    else:
        raise ValueError(f"Invalid method: {method}")

    # We should never use more bins than the number of possible values.
    n_bins = min(n_bins, np.unique(data).size)
    # TODO: Alternatively, only for discrete data
    # if is_discrete(data):
    #     n_bins = min(data_range, n_bins)

    return n_bins


def compare_smart_bins(data: ArrayLike, subplots_kwargs: dict = None, hist_kwargs: dict = None) -> Figure:
    """

    Parameters
    ----------
    subplots_kwargs
        Additional keyword arguments are documented in :func:`matplotlib.pyplot.subplots`.
    hist_kwargs
        Additional keyword arguments are documented in :meth:`DataFrame.plot`.


    """
    import matplotlib.pyplot as plt
    import pandas as pd

    kwargs = dict(figsize=(10, 9), nrows=3, ncols=2, sharex=True, sharey=True)
    kwargs.update(subplots_kwargs if subplots_kwargs else {})
    assert len(SMART_BIN_METHODS) == 6
    assert kwargs["nrows"] * kwargs["ncols"] == 6, "Expected 6 axes (e.g. 3 rows and 2 columns)"
    fig, axes = plt.subplots(squeeze=False, **kwargs)
    series = pd.Series(data)

    for method, ax in zip(SMART_BIN_METHODS, axes.flatten()):
        kwargs = dict(density=True)
        kwargs.update(hist_kwargs if hist_kwargs else {})
        bins = smart_bins(data, method)
        series.plot.hist(bins=bins, ax=ax, **kwargs)
        ax.set_title(f"{method} (bins={bins})")

    return fig
