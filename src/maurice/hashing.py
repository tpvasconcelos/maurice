from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import dill

from maurice.utils import optional_import

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd
else:
    pd = optional_import("pandas")
    np = optional_import("numpy")

_DFLT_HASH = "md5"


def hash_anything(
    obj: Any,
    hash_name: str = _DFLT_HASH,
) -> str:
    # TODO: explore DeepDiff's DeepHash?
    if pd and isinstance(obj, (pd.DataFrame, pd.Series, pd.Index)):
        return hash_pandas_dataframe(obj, hash_name=hash_name)
    if np and isinstance(obj, np.ndarray):
        return hash_numpy_ndarray(obj, hash_name=hash_name)
    return hashlib.new(hash_name, dill.dumps(obj)).hexdigest()


def hash_numpy_ndarray(arr: np.ndarray, hash_name: str = _DFLT_HASH, **kwargs: Any) -> str:
    from pandas.core.util.hashing import combine_hash_arrays

    hashes = (pd.util.hash_array(arr, **kwargs) for _ in [...])
    hashes_array = combine_hash_arrays(hashes, num_items=len(arr))
    return hashlib.new(hash_name, hashes_array).hexdigest()


def hash_pandas_dataframe(
    df: pd.DataFrame | pd.Series | pd.Index,
    sort_columns: bool = True,
    sort_rows: bool = True,
    hash_name: str = _DFLT_HASH,
    **kwargs: Any,
) -> str:
    if sort_columns:
        df = df.sort_index(axis="columns")
    row_hashes_array = pd.util.hash_pandas_object(obj=df, **kwargs).to_numpy()
    if sort_rows:
        row_hashes_array.sort()
    return hashlib.new(hash_name, row_hashes_array).hexdigest()


if __name__ == "__main__":
    for df in [
        pd.DataFrame({"a": [1, 2, 3], "b": ["a", "b", "c"]}, index=[1, 2, 3]),
        pd.DataFrame({"a": [3, 2, 1], "b": ["c", "b", "a"]}, index=[3, 2, 1]).sort_index(),
        pd.DataFrame({"a": [3, 2, 1], "b": ["c", "b", "a"]}, index=[3, 2, 1]),
        pd.DataFrame({"b": ["c", "b", "a"], "a": [3, 2, 1]}, index=[3, 2, 1]),
        pd.DataFrame({"a": [1, 2, 3], "b": ["a", "b", "c"]}, index=[3, 2, 1]),
        pd.DataFrame({"a": [1, 2, 3], "b": ["a", "b", "c"]}, index=[3, 2, 1]).sort_index(),
    ]:
        print(hash_pandas_dataframe(df, sort_columns=True, sort_rows=True))
