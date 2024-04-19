import logging

from tensorflow.python.keras.models import Model

from maurice.patchers.core import patch_method_with_caching

logger = logging.getLogger(__name__)


def caching_patch_keras_models() -> None:
    logger.debug("Patching Keras' Model (CACHING)...")
    patch_method_with_caching(name="fit", cls=Model, save_state=True)
