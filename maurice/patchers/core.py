import logging
from types import MethodType

import dill
import wrapt

from maurice.caching import CACHE_DIR
from maurice.utils import hash_any

logger = logging.getLogger(__name__)


class CachingMethodWrapper(object):
    def __init__(self, instance: type, method: MethodType, args, kwargs):
        self._instance = instance
        self._method = method
        self._args = args
        self._kwargs = kwargs

        self._path_to_cached_method = CACHE_DIR.joinpath(
            # path to module
            *type(instance).__module__.split("."),
            # class name
            type(instance).__name__,
            # instance state hash
            hash_any(self._get_instance_state()),
            # instance method name
            method.__name__,
            # args and kwargs hash
            hash_any((args, kwargs)),
        )
        self._path_to_state = self._path_to_cached_method.joinpath("state.dill")
        self._path_to_result = self._path_to_cached_method.joinpath("result.dill")

    def _get_instance_state(self):
        if hasattr(self._instance, "__getstate__"):
            state = self._instance.__getstate__()
        else:
            state = self._instance.__dict__
        return state

    def _set_instance_state(self, state) -> None:
        if hasattr(self._instance, "__setstate__"):
            self._instance.__setstate__(state)
        else:
            self._instance.__dict__.update(state)

    def run_wrapped(self):
        if not self._path_to_cached_method.exists():
            result = self._method(*self._args, **self._kwargs)
            logger.info(f"Saving cache to: {self._path_to_cached_method}")
            self._path_to_cached_method.mkdir(parents=True, exist_ok=False)
            self._path_to_state.write_bytes(dill.dumps(self._get_instance_state()))
            self._path_to_result.write_bytes(dill.dumps(result))
            return result
        else:
            logger.info(f"Loading cache from: {self._path_to_cached_method}")
            self._set_instance_state(dill.loads(self._path_to_state.read_bytes()))
            result = dill.loads(self._path_to_result.read_bytes())
        return result


def _caching_method_wrapper(method: MethodType, instance: type, args, kwargs):
    return CachingMethodWrapper(instance=instance, method=method, args=args, kwargs=kwargs).run_wrapped()


def patch_method_with_caching(name: str, cls: type) -> None:
    wrapt.wrap_function_wrapper(module=cls.__module__, name=f"{cls.__name__}.{name}", wrapper=_caching_method_wrapper)
