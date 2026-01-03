from __future__ import annotations

import logging
from types import ModuleType

import wrapt
from pandas.io.sql import SQLDatabase, SQLiteDatabase

from maurice.patchers.core import patch_method_with_caching

logger = logging.getLogger(__name__)


def _caching_patch_pandas_db(module: ModuleType) -> None:
    logger.debug("Patching pandas SQLDatabase and SQLiteDatabase (CACHING)...")
    dbs = (SQLDatabase, SQLiteDatabase)
    for cls in dbs:
        patch_method_with_caching(name="read_query", cls=cls, save_state=False)


def register_post_import_hook() -> None:
    wrapt.register_post_import_hook(
        _caching_patch_pandas_db,
        "sklearn",
    )
