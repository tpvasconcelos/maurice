import logging

from tensorflow.python.keras.models import Model

from maurice.patchers.core import wrap_fit_method

logger = logging.getLogger(__name__)


def patch_keras_models() -> None:
    logger.debug("Patching Keras models...")
    wrap_fit_method(classes=(Model,))
