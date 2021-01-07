import logging

from sklearn.utils import all_estimators

from maurice.patchers.core import patch_method_with_caching

logger = logging.getLogger(__name__)


def caching_patch_sklearn_estimators() -> None:
    logger.debug("Patching sklearn estimators (CACHING)...")
    for cls in tuple(zip(*all_estimators()))[1]:
        patch_method_with_caching(name="fit", cls=cls, save_state=True)
