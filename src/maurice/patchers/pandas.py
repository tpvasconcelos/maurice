import logging

from pandas.io.sql import SQLDatabase, SQLiteDatabase

from maurice.patchers.core import patch_method_with_caching

logger = logging.getLogger(__name__)


def caching_patch_pandas_db() -> None:
    logger.debug("Patching pandas SQLDatabase and SQLiteDatabase (CACHING)...")
    dbs = (SQLDatabase, SQLiteDatabase)
    for cls in dbs:
        patch_method_with_caching(name="read_query", cls=cls, save_state=False)
