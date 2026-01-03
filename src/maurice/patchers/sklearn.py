from __future__ import annotations

import logging
from types import ModuleType
from typing import Any

import wrapt

from maurice.patchers.core import patch_method_with_caching

logger = logging.getLogger(__name__)


def implements(cls: type[Any], method_name: str) -> bool:
    return callable(getattr(cls, method_name, None))


def _caching_patch_sklearn_estimators(module: ModuleType) -> None:
    from sklearn.utils import all_estimators

    logger.debug("Patching sklearn estimators (CACHING)...")
    for cls in tuple(zip(*all_estimators()))[1]:
        patch_method_with_caching(name="fit", cls=cls, save_state=True)
        if implements(cls, "predict"):
            patch_method_with_caching(name="predict", cls=cls, save_state=True)
        if implements(cls, "transform"):
            patch_method_with_caching(name="transform", cls=cls, save_state=True)


def register_post_import_hook() -> None:
    wrapt.register_post_import_hook(
        _caching_patch_sklearn_estimators,
        "sklearn",
    )
