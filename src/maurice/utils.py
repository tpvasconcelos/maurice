from __future__ import annotations

import logging
import sys
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

_not_importable = set()


def optional_import(name: str) -> ModuleType | None:
    """Try to import an optional module.

    Parameters
    ----------
    name : str
        Absolute name of the module to import. E.g. 'scipy.stats'.

    Raises
    ------
    Exception
        Any exception raised while importing a module is propagated,
        unless the exception raised in an :exc:`ImportError`.

    Returns
    -------
    Returns the module if the import was successful or if the modelule is
    already present in ``sys.modules``. Otherwise, returns None.

    ..
        Implementation inspired by: _plotly_utils/optional_imports.py

    """
    if name in _not_importable:
        return None

    try:
        return sys.modules[name]
    except KeyError:
        pass

    try:
        return import_module(name)
    except ImportError:
        _not_importable.add(name)
    # except Exception:
    #     _not_importable.add(name)
    #     logger.exception(f"Error importing optional module '{name}'")
    return None


def _setup_debug_logging(level=logging.DEBUG) -> None:
    for handler in (root_logger := logging.getLogger()).handlers[:]:
        root_logger.removeHandler(handler)

    logger = logging.getLogger("maurice")
    logger.setLevel(level)
    logger.handlers.clear()

    handler = logging.StreamHandler()
    fmt = "[%(levelname)-7s][%(pathname)s:%(lineno)d] %(message)s"
    handler.setFormatter(logging.Formatter(fmt))

    handler.setLevel(level)
    logger.addHandler(handler)

    logger.debug(f"Finished setting up {logger} with {handler}")
