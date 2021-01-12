import logging
from abc import ABCMeta, abstractmethod
from functools import partial
from typing import Any, Optional

import dill
import wrapt

from maurice.caching import CACHE_DIR
from maurice.types import BoundMethodClassType, BoundMethodInstanceType, BoundMethodReturnType, BoundMethodType
from maurice.utils import hash_any

logger = logging.getLogger(__name__)


class BaseMethodWrapper(metaclass=ABCMeta):
    """
    Notes:
        - The `__method` attribute should remain a `private` attribute. I cannot foresee the need to access `__method`
        from a subclass of  `BaseMethodWrapper`.
        - The `_args` and `_kwargs` methods belong to the private API and therefore accessible to all subclasses of
        `BaseMethodWrapper`. This way, you are able to overwrite or mutate them before a method call.
    """

    def __init__(self, method: BoundMethodType, args: tuple, kwargs: dict):
        self.__method: BoundMethodType = method
        self._args: tuple = args
        self._kwargs: dict = kwargs

    @property
    def _instance(self) -> BoundMethodInstanceType:
        return self.__method.__self__

    # noinspection PyMethodMayBeStatic
    def _run_before(self) -> bool:
        return True

    # noinspection PyMethodMayBeStatic
    def _run_after(self, result: Optional[BoundMethodReturnType]) -> Any:
        return result

    def run(self) -> Any:
        result = None
        if self._run_before():
            result = self.__method(*self._args, **self._kwargs)
        return self._run_after(result=result)


class CachingMethodWrapper(BaseMethodWrapper):
    def __init__(self, method: BoundMethodType, args: tuple, kwargs: dict, save_state: bool):
        super(CachingMethodWrapper, self).__init__(method=method, args=args, kwargs=kwargs)
        self._save_state: bool = save_state

        state_string = hash_any(self._get_instance_state()) if self._save_state else "ignore_state"
        self._path_to_cached_method = CACHE_DIR.joinpath(
            # path to module
            *type(self._instance).__module__.split("."),
            # class name
            type(self._instance).__name__,
            # instance state hash
            state_string,
            # instance method name
            method.__name__,
            # args and kwargs hash
            hash_any((args, kwargs)),
        )
        self._path_to_state = self._path_to_cached_method.joinpath("state.dill")
        self._path_to_result = self._path_to_cached_method.joinpath("result.dill")

    def _get_instance_state(self) -> dict:
        if hasattr(self._instance, "__getstate__"):
            state: dict = getattr(self._instance, "__getstate__")()
        else:
            state = self._instance.__dict__
        return state

    def _set_instance_state(self, state: dict) -> None:
        if hasattr(self._instance, "__setstate__"):
            getattr(self._instance, "__setstate__")(state)
        else:
            self._instance.__dict__.update(state)

    def _run_before(self) -> bool:
        return not self._path_to_cached_method.exists()

    def _run_after(self, result: Optional[BoundMethodReturnType]) -> Any:
        if result:
            logger.info(f"Saving cache to: {self._path_to_cached_method}")
            self._path_to_cached_method.mkdir(parents=True, exist_ok=False)
            if self._save_state:
                self._path_to_state.write_bytes(dill.dumps(self._get_instance_state()))
            self._path_to_result.write_bytes(dill.dumps(result))
        else:
            logger.info(f"Loading cache from: {self._path_to_cached_method}")
            if self._save_state:
                self._set_instance_state(dill.loads(self._path_to_state.read_bytes()))
            result = dill.loads(self._path_to_result.read_bytes())
        return result


def _caching_method_wrapper(
    method: BoundMethodType, _: BoundMethodInstanceType, args: tuple, kwargs: dict, save_state: bool
) -> Any:
    return CachingMethodWrapper(method=method, args=args, kwargs=kwargs, save_state=save_state).run()


def patch_method_by_name(name: str, cls: type) -> None:
    pass


def patch_method_with_caching(name: str, cls: BoundMethodClassType, save_state: bool) -> None:
    wrapt.wrap_function_wrapper(
        module=cls.__module__,
        name=f"{cls.__name__}.{name}",
        wrapper=partial(_caching_method_wrapper, save_state=save_state),
    )
