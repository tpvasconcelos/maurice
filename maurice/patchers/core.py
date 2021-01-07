import logging
from types import MethodType
from typing import Callable

import dill
import wrapt
from sklearn.base import BaseEstimator

from maurice.caching import CACHE_DIR
from maurice.utils import hash_any

logger = logging.getLogger(__name__)

def get_path_to_cached_callable(callable: Callable) -> Path:
    path_to_cache = CACHE_DIR.joinpath(
        # path to module
        *type(instance).__module__.split("."),
        # class name
        type(instance).__name__,
        # instance state hash
        hash_any(instance.__getstate__()),
        # instance method name
        wrapped.__name__,
        # args and kwargs hash
        hash_any((args, kwargs)),
    )

def fit_caching_wrapper(wrapped: MethodType, instance: BaseEstimator, args, kwargs) -> BaseEstimator:
    path_to_cache = CACHE_DIR.joinpath(
        # path to module
        *type(instance).__module__.split("."),
        # class name
        type(instance).__name__,
        # instance state hash
        hash_any(instance.__getstate__()),
        # instance method name
        wrapped.__name__,
        # args and kwargs hash
        hash_any((args, kwargs)),
    )
    path_to_state = path_to_cache.joinpath("state.dill")
    path_to_result = path_to_cache.joinpath("result.dill")

    if not path_to_cache.exists():
        result = wrapped(*args, **kwargs)
        logger.info(f"Saving cache to: {path_to_cache}")
        path_to_cache.mkdir(parents=True, exist_ok=False)
        path_to_state.write_bytes(dill.dumps(instance.__getstate__()))
        path_to_result.write_bytes(dill.dumps(result))
        return result
    else:
        logger.info(f"Loading cache from: {path_to_cache}")
        instance.__setstate__(dill.loads(path_to_state.read_bytes()))
        result = dill.loads(path_to_result.read_bytes())

    return result


def wrap_fit_method(classes) -> None:
    for c in classes:
        wrapt.wrap_function_wrapper(c.__module__, f"{c.__name__}.fit", fit_caching_wrapper)
