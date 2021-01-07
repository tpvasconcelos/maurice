import logging

from sklearn.utils import all_estimators

from maurice.patchers.core import wrap_fit_method

logger = logging.getLogger(__name__)


def patch_sklearn_estimators() -> None:
    logger.debug("Patching sklearn estimators...")
    wrap_fit_method(classes=tuple(zip(*all_estimators()))[1])
