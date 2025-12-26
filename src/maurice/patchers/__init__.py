from __future__ import annotations

from maurice.utils import optional_import


def patch() -> None:
    if optional_import("sklearn"):
        from maurice.patchers.sklearn import caching_patch_sklearn_estimators

        caching_patch_sklearn_estimators()
    if optional_import("pandas"):
        from maurice.patchers.pandas import caching_patch_pandas_db

        caching_patch_pandas_db()
