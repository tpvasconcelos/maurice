from maurice.patchers.pandas import caching_patch_pandas_db
from maurice.patchers.sklearn import caching_patch_sklearn_estimators


def patch() -> None:
    caching_patch_sklearn_estimators()
    caching_patch_pandas_db()
