from __future__ import annotations

import copyreg
import json
import logging
from abc import ABCMeta
from dataclasses import dataclass, field
from functools import cached_property, partial
from pathlib import Path
from typing import Any

import dill
import wrapt

from maurice._missing import MISSING, MissingType
from maurice.hashing import hash_anything
from maurice.types import (
    BoundMethodClassType,
    BoundMethodInstanceType,
    BoundMethodType,
)

logger = logging.getLogger(__name__)


@dataclass
class ArgsKwargs:
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)


@dataclass
class PreHookResult:
    run_wrapped_method: bool = True
    run_post_hook: bool = True
    new_args_kwargs: ArgsKwargs | None = None


class BaseMethodWrapper(metaclass=ABCMeta):
    """
    Notes
    -----
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

    def _pre_hook(self) -> PreHookResult:
        return PreHookResult()

    def _post_hook(self, result: Any | MissingType) -> Any:
        return result

    def run(self) -> Any:
        # Initialize result as MISSING to detect misconfigurations.
        # The result should be set by calling the wrapped
        # method, by the post-hook, or by both.
        result = MISSING

        # Start by calling the pre-hook.
        # The pre-hook result determines whether to call the wrapped method,
        # which arguments to pass to it (if any), and whether to call the post-hook.
        pre_hook_result = self._pre_hook()

        if pre_hook_result.run_wrapped_method:
            if pre_hook_result.new_args_kwargs is not None:
                args = pre_hook_result.new_args_kwargs.args
                kwargs = pre_hook_result.new_args_kwargs.kwargs
            else:
                args, kwargs = self._args, self._kwargs
            result = self.__method(*args, **kwargs)

        if pre_hook_result.run_post_hook:
            result = self._post_hook(result)

        if result is MISSING:
            raise RuntimeError(
                f"Misconfigured implementation of {type(self).__name__}: "
                "the wrapped method result was not set. The result should be set "
                "by calling the wrapped method, by the post-hook, or by both."
            )

        return result


class CachingMethodWrapper(BaseMethodWrapper):
    def __init__(self, method: BoundMethodType, args: tuple, kwargs: dict, save_state: bool):
        super(CachingMethodWrapper, self).__init__(method=method, args=args, kwargs=kwargs)
        self._save_state = save_state

        state_string = (
            hash_anything(self._get_instance_state()) if self._save_state else "_ignore_state"
        )
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
            hash_anything((args, kwargs)),
        )
        self._path_to_state = self._path_to_cached_method / "state.dill"
        self._path_to_result = self._path_to_cached_method / "result.dill"

    def _get_instance_state(self) -> dict:
        if hasattr(self._instance, "__getstate__"):
            state: dict = self._instance.__getstate__()
        else:
            state = self._instance.__dict__
        return state

    def _set_instance_state(self, state: dict) -> None:
        if hasattr(self._instance, "__setstate__"):
            self._instance.__setstate__(state)
        else:
            self._instance.__dict__.update(state)

    def _pre_hook(self) -> PreHookResult:
        return PreHookResult(
            run_wrapped_method=not self._path_to_cached_method.exists(),
        )

    def _post_hook(self, result: Any | MissingType) -> Any:
        if result is MISSING:
            logger.info(f"Loading cache from: {self._path_to_cached_method}")
            if self._save_state:
                self._set_instance_state(dill.loads(self._path_to_state.read_bytes()))
            return dill.loads(self._path_to_result.read_bytes())

        logger.info(f"Saving cache to: {self._path_to_cached_method}")
        self._path_to_cached_method.mkdir(parents=True, exist_ok=False)
        if self._save_state:
            self._path_to_state.write_bytes(dill.dumps(self._get_instance_state()))
        self._path_to_result.write_bytes(dill.dumps(result))
        return result


CACHE_DIR = Path.cwd().joinpath(".maurice_cache").absolute()


def _get_state(obj: Any) -> dict:
    if hasattr(obj, "__getstate__"):
        state: dict = obj.__getstate__()
    elif hasattr(obj, "__dict__"):
        state = obj.__dict__
    elif hasattr(obj, "__slots__"):
        state = {attr: getattr(obj, attr) for attr in copyreg._slotnames()}
    else:
        raise TypeError(f"Object of type {type(obj)} not serializable")
    return state


def _set_state(obj: Any, state: dict) -> None:
    if hasattr(obj, "__setstate__"):
        obj.__setstate__(state)
    elif hasattr(obj, "__dict__"):
        obj.__dict__.update(state)
    elif hasattr(obj, "__slots__"):
        for attr in state:
            setattr(obj, attr, state[attr])
    else:
        raise TypeError(f"Object of type {type(obj)} not serializable")


class MethodCacheManager:
    def __init__(
        self,
        method: BoundMethodType,
        args: tuple,
        kwargs: dict,
        stateful: bool,
    ) -> None:
        self.method: BoundMethodType = method
        self.args: tuple = args
        self.kwargs: dict = kwargs
        self.stateful: bool = stateful

        self._initial_instance_state = _get_state(self.method.__self__)

    @property
    def instance(self) -> BoundMethodInstanceType:
        return self.method.__self__

    @cached_property
    def state_string(self) -> str:
        return hash_anything(self._get_instance_state()) if self.stateful else "_stateless"

    @cached_property
    def parent_dir(self) -> Path:
        return CACHE_DIR.joinpath(
            # path to module
            *type(self.instance).__module__.split("."),
            # class name
            type(self.instance).__name__,
            # instance state hash
            self.state_string,
            # instance method name
            self.method.__name__,
            # args and kwargs hash
            hash_anything((self.args, self.kwargs)),
        )

    @property
    def state(self) -> Path:
        return self.parent_dir / "state.dill"

    @property
    def result(self) -> Path:
        return self.parent_dir / "result.dill"

    @property
    def metadata(self) -> Path:
        return self.parent_dir / "metadata.json"

    def exists(self) -> bool:
        return self.parent_dir.exists()

    def read(self) -> Any:
        if self.stateful:
            self._set_instance_state(state=dill.loads(self.state.read_bytes()))
        return dill.loads(self.result.read_bytes())

    def write(self, result: Any):
        self.parent_dir.mkdir(parents=True, exist_ok=False)
        if self.stateful:
            state = self._get_instance_state()
            self.state.write_bytes(dill.dumps(state))
        else:
            state = None

        self.result.write_bytes(dill.dumps(result))
        self.metadata.write_text(
            json.dumps(
                {
                    "method": self.method.__name__,
                    "args": repr(self.args),
                    "kwargs": repr(self.kwargs),
                    "stateful": self.stateful,
                    "state": repr(state),
                    "state_hash": hash_anything(state),
                    "result": repr(result),
                    "result_hash": hash_anything(result),
                },
                indent=2,
            )
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.parent_dir})"


def run_cached_method(
    method: BoundMethodType,
    args: tuple,
    kwargs: dict,
    save_state: bool,
) -> Any:
    cache = MethodCacheManager(
        method=method,
        args=args,
        kwargs=kwargs,
        stateful=save_state,
    )

    if cache.exists():
        logger.info(f"Loading cache from: {cache}")
        return cache.read()

    result = method(*args, **kwargs)
    logger.info(f"Saving cache to: {cache}")
    cache.write(result)

    return result


def _caching_method_wrapper(
    method: BoundMethodType,
    _: BoundMethodInstanceType,
    args: tuple,
    kwargs: dict,
    save_state: bool,
    cmw_class: type[CachingMethodWrapper],
) -> Any:
    return run_cached_method(
        method=method,
        args=args,
        kwargs=kwargs,
        save_state=save_state,
    )
    # return cmw_class(
    #     method=method,
    #     args=args,
    #     kwargs=kwargs,
    #     save_state=save_state,
    # ).run()


def patch_method_with_caching(
    name: str,
    cls: BoundMethodClassType,
    save_state: bool,
    cmw_class: type[CachingMethodWrapper] = CachingMethodWrapper,
) -> None:
    wrapt.wrap_function_wrapper(
        target=cls,
        name=name,
        wrapper=partial(_caching_method_wrapper, save_state=save_state, cmw_class=cmw_class),
    )
