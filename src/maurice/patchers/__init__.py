from __future__ import annotations


def patch() -> None:
    from maurice.patchers.pandas import register_post_import_hook as register_pandas
    from maurice.patchers.sklearn import register_post_import_hook as register_sklearn

    register_sklearn()
    register_pandas()
