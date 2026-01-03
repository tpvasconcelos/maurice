from __future__ import annotations

import copy
import functools
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class AttributeChange:
    """Represents a single attribute change."""

    name: str
    change_type: ChangeType
    old_value: Any = None
    new_value: Any = None
    path: str = ""  # For nested changes, e.g., "obj.nested.attr"

    def __repr__(self):
        path_str = self.path or self.name
        if self.change_type == ChangeType.ADDED:
            return f"ADDED: {path_str} = {self.new_value!r}"
        if self.change_type == ChangeType.REMOVED:
            return f"REMOVED: {path_str} (was {self.old_value!r})"
        return f"MODIFIED: {path_str}: {self.old_value!r} -> {self.new_value!r}"


@dataclass
class StateChangeResult:
    """Contains all detected changes from a method call."""

    method_name: str
    changes: list[AttributeChange] = field(default_factory=list)
    exception_raised: Exception | None = None
    return_value: Any = None

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    @property
    def added(self) -> list[AttributeChange]:
        return [c for c in self.changes if c.change_type == ChangeType.ADDED]

    @property
    def removed(self) -> list[AttributeChange]:
        return [c for c in self.changes if c.change_type == ChangeType.REMOVED]

    @property
    def modified(self) -> list[AttributeChange]:
        return [c for c in self.changes if c.change_type == ChangeType.MODIFIED]

    def get_changes_for_path(self, path: str) -> list[AttributeChange]:
        return [c for c in self.changes if c.path == path or c.name == path]

    def __repr__(self):
        lines = [f"StateChangeResult(method='{self.method_name}', changes={len(self.changes)})"]
        for change in self.changes:
            lines.append(f"  {change}")
        if self.exception_raised:
            lines.append(f"  EXCEPTION: {self.exception_raised}")
        return "\n".join(lines)


class StateChangeDetector:
    """
    Detects changes in object state after method calls.

    Usage:
        detector = StateChangeDetector(my_object)
        result = detector.call('method_name', arg1, arg2, kwarg=value)
        print(result.changes)

        # Or use as context manager
        with detector.track() as tracker:
            my_object.some_method()
        print(tracker.changes)

        # Or wrap the entire object
        wrapped = detector.wrap()
        wrapped.some_method()  # Automatically tracked
        print(detector.last_result)
    """

    def __init__(
        self,
        obj: Any,
        deep: bool = True,
        max_depth: int = 10,
        ignore_private: bool = False,
        ignore_dunder: bool = True,
        track_collections: bool = True,
    ):
        self._obj = obj
        self._deep = deep
        self._max_depth = max_depth
        self._ignore_private = ignore_private
        self._ignore_dunder = ignore_dunder
        self._track_collections = track_collections
        self._last_result: StateChangeResult | None = None
        self._seen_ids: set[int] = set()  # For circular reference detection

    @property
    def last_result(self) -> StateChangeResult | None:
        return self._last_result

    def _should_ignore_attr(self, name: str) -> bool:
        """Determine if an attribute should be ignored."""
        if self._ignore_dunder and name.startswith("__") and name.endswith("__"):
            return True
        if self._ignore_private and name.startswith("_"):
            return True
        return False

    def _get_all_attributes(self, obj: Any) -> dict[str, Any]:
        """Extract all attributes from an object, handling various object types."""
        attrs = {}

        # Handle slots-based classes
        slots = set()
        for cls in type(obj).__mro__:
            if hasattr(cls, "__slots__"):
                slots.update(cls.__slots__)

        # Get slot attributes
        for slot in slots:
            if not self._should_ignore_attr(slot):
                try:
                    attrs[slot] = getattr(obj, slot)
                except AttributeError:
                    pass  # Slot not initialized

        # Get __dict__ attributes if available
        if hasattr(obj, "__dict__"):
            for name, value in obj.__dict__.items():
                if not self._should_ignore_attr(name):
                    attrs[name] = value

        return attrs

    def _deep_copy_safe(self, obj: Any, memo: dict | None = None) -> Any:
        """Safely deep copy an object, handling uncopyable objects."""
        if memo is None:
            memo = {}

        obj_id = id(obj)
        if obj_id in memo:
            return memo[obj_id]

        try:
            copied = copy.deepcopy(obj, memo)
            memo[obj_id] = copied
            return copied
        except (TypeError, copy.Error, RecursionError):
            # Object can't be deep copied, try shallow copy
            try:
                copied = copy.copy(obj)
                memo[obj_id] = copied
                return copied
            except (TypeError, copy.Error):
                # Return a marker for uncopyable objects
                return _UncopyableMarker(type(obj).__name__, obj_id)

    def _snapshot(self, obj: Any) -> dict[str, Any]:
        """Create a snapshot of object state."""
        attrs = self._get_all_attributes(obj)
        if self._deep:
            return {k: self._deep_copy_safe(v) for k, v in attrs.items()}
        return dict(attrs)

    def _compare_values(
        self, old: Any, new: Any, path: str, depth: int = 0
    ) -> list[AttributeChange]:
        """Deep compare two values and return changes."""
        changes = []

        if depth > self._max_depth:
            if old != new:
                changes.append(
                    AttributeChange(
                        name=path.split(".")[-1],
                        change_type=ChangeType.MODIFIED,
                        old_value="<max depth reached>",
                        new_value="<max depth reached>",
                        path=path,
                    )
                )
            return changes

        # Handle uncopyable markers
        if isinstance(old, _UncopyableMarker) or isinstance(new, _UncopyableMarker):
            if old != new:
                changes.append(
                    AttributeChange(
                        name=path.split(".")[-1],
                        change_type=ChangeType.MODIFIED,
                        old_value=old,
                        new_value=new,
                        path=path,
                    )
                )
            return changes

        # Check for circular references
        old_id, new_id = id(old), id(new)
        if old_id in self._seen_ids and new_id in self._seen_ids:
            return changes
        self._seen_ids.add(old_id)
        self._seen_ids.add(new_id)

        try:
            # Same object or equal
            if old is new or old == new:
                return changes
        except Exception:
            # Comparison failed, check identity only
            if old is new:
                return changes

        # Type changed
        if type(old) != type(new):
            changes.append(
                AttributeChange(
                    name=path.split(".")[-1],
                    change_type=ChangeType.MODIFIED,
                    old_value=old,
                    new_value=new,
                    path=path,
                )
            )
            return changes

        # Deep comparison for collections
        if self._track_collections:
            if isinstance(old, dict) and isinstance(new, dict):
                changes.extend(self._compare_dicts(old, new, path, depth))
                return changes

            if isinstance(old, (list, tuple)) and isinstance(new, (list, tuple)):
                changes.extend(self._compare_sequences(old, new, path, depth))
                return changes

            if isinstance(old, set) and isinstance(new, set):
                changes.extend(self._compare_sets(old, new, path))
                return changes

        # Deep comparison for objects with __dict__
        if hasattr(old, "__dict__") and hasattr(new, "__dict__"):
            old_attrs = self._get_all_attributes(old)
            new_attrs = self._get_all_attributes(new)
            changes.extend(self._compare_attr_dicts(old_attrs, new_attrs, path, depth))
            return changes

        # Values are different
        changes.append(
            AttributeChange(
                name=path.split(".")[-1],
                change_type=ChangeType.MODIFIED,
                old_value=old,
                new_value=new,
                path=path,
            )
        )
        return changes

    def _compare_dicts(self, old: dict, new: dict, path: str, depth: int) -> list[AttributeChange]:
        changes = []
        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            key_path = f"{path}[{key!r}]"
            if key not in old:
                changes.append(
                    AttributeChange(
                        name=str(key),
                        change_type=ChangeType.ADDED,
                        new_value=new[key],
                        path=key_path,
                    )
                )
            elif key not in new:
                changes.append(
                    AttributeChange(
                        name=str(key),
                        change_type=ChangeType.REMOVED,
                        old_value=old[key],
                        path=key_path,
                    )
                )
            else:
                changes.extend(self._compare_values(old[key], new[key], key_path, depth + 1))
        return changes

    def _compare_sequences(self, old, new, path: str, depth: int) -> list[AttributeChange]:
        changes = []
        if len(old) != len(new):
            changes.append(
                AttributeChange(
                    name=path.split(".")[-1],
                    change_type=ChangeType.MODIFIED,
                    old_value=f"length={len(old)}",
                    new_value=f"length={len(new)}",
                    path=f"{path}.length",
                )
            )

        for i, (o, n) in enumerate(zip(old, new)):
            changes.extend(self._compare_values(o, n, f"{path}[{i}]", depth + 1))

        # Track added items
        if len(new) > len(old):
            for i in range(len(old), len(new)):
                changes.append(
                    AttributeChange(
                        name=str(i),
                        change_type=ChangeType.ADDED,
                        new_value=new[i],
                        path=f"{path}[{i}]",
                    )
                )
        # Track removed items
        elif len(old) > len(new):
            for i in range(len(new), len(old)):
                changes.append(
                    AttributeChange(
                        name=str(i),
                        change_type=ChangeType.REMOVED,
                        old_value=old[i],
                        path=f"{path}[{i}]",
                    )
                )
        return changes

    def _compare_sets(self, old: set, new: set, path: str) -> list[AttributeChange]:
        changes = []
        for item in new - old:
            changes.append(
                AttributeChange(
                    name="set_item",
                    change_type=ChangeType.ADDED,
                    new_value=item,
                    path=f"{path}.add({item!r})",
                )
            )
        for item in old - new:
            changes.append(
                AttributeChange(
                    name="set_item",
                    change_type=ChangeType.REMOVED,
                    old_value=item,
                    path=f"{path}.remove({item!r})",
                )
            )
        return changes

    def _compare_attr_dicts(
        self, old: dict, new: dict, base_path: str, depth: int
    ) -> list[AttributeChange]:
        changes = []
        all_attrs = set(old.keys()) | set(new.keys())

        for attr in all_attrs:
            path = f"{base_path}.{attr}" if base_path else attr
            if attr not in old:
                changes.append(
                    AttributeChange(
                        name=attr, change_type=ChangeType.ADDED, new_value=new[attr], path=path
                    )
                )
            elif attr not in new:
                changes.append(
                    AttributeChange(
                        name=attr, change_type=ChangeType.REMOVED, old_value=old[attr], path=path
                    )
                )
            else:
                changes.extend(self._compare_values(old[attr], new[attr], path, depth + 1))
        return changes

    def _detect_changes(self, before: dict, after: dict) -> list[AttributeChange]:
        """Compare before and after snapshots."""
        self._seen_ids.clear()
        return self._compare_attr_dicts(before, after, "", 0)

    def call(self, method_name: str, *args, **kwargs) -> StateChangeResult:
        """Call a method on the object and detect state changes."""
        method = getattr(self._obj, method_name)
        if not callable(method):
            raise TypeError(f"'{method_name}' is not callable")

        before = self._snapshot(self._obj)
        result = StateChangeResult(method_name=method_name)

        try:
            result.return_value = method(*args, **kwargs)
        except Exception as e:
            result.exception_raised = e

        after = self._snapshot(self._obj)
        result.changes = self._detect_changes(before, after)
        self._last_result = result
        return result

    @contextmanager
    def track(self):
        """Context manager to track changes during a block of code."""
        before = self._snapshot(self._obj)
        result = StateChangeResult(method_name="<context_block>")

        try:
            yield result
        except Exception as e:
            result.exception_raised = e
            raise
        finally:
            after = self._snapshot(self._obj)
            result.changes = self._detect_changes(before, after)
            self._last_result = result

    def wrap(self) -> TrackedObjectProxy:
        """Return a proxy that tracks all method calls."""
        return TrackedObjectProxy(self)

    def decorator(self, method: Callable) -> Callable:
        """Decorator to track changes for a specific method."""

        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            before = self._snapshot(self._obj)
            result = StateChangeResult(method_name=method.__name__)

            try:
                result.return_value = method(*args, **kwargs)
            except Exception as e:
                result.exception_raised = e
                raise
            finally:
                after = self._snapshot(self._obj)
                result.changes = self._detect_changes(before, after)
                self._last_result = result

            return result.return_value

        return wrapper


class _UncopyableMarker:
    """Marker for objects that cannot be copied."""

    def __init__(self, type_name: str, obj_id: int):
        self.type_name = type_name
        self.obj_id = obj_id

    def __repr__(self):
        return f"<Uncopyable: {self.type_name} at {self.obj_id}>"

    def __eq__(self, other):
        if isinstance(other, _UncopyableMarker):
            return self.obj_id == other.obj_id
        return False


class TrackedObjectProxy:
    """Proxy that intercepts method calls and tracks changes."""

    def __init__(self, detector: StateChangeDetector):
        object.__setattr__(self, "_detector", detector)
        object.__setattr__(self, "_results", [])

    def __getattr__(self, name: str):
        obj = object.__getattribute__(self, "_detector")._obj
        attr = getattr(obj, name)

        if callable(attr):

            @functools.wraps(attr)
            def tracked_method(*args, **kwargs):
                detector = object.__getattribute__(self, "_detector")
                result = detector.call(name, *args, **kwargs)
                object.__getattribute__(self, "_results").append(result)
                if result.exception_raised:
                    raise result.exception_raised
                return result.return_value

            return tracked_method
        return attr

    def __setattr__(self, name: str, value: Any):
        obj = object.__getattribute__(self, "_detector")._obj
        setattr(obj, name, value)

    def get_all_results(self) -> list[StateChangeResult]:
        return object.__getattribute__(self, "_results")

    def get_unwrapped(self):
        return object.__getattribute__(self, "_detector")._obj


# Decorator for class methods
def track_changes(detector_attr: str = "_detector"):
    """Class decorator or method decorator to enable change tracking."""

    def method_decorator(method: Callable) -> Callable:
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            detector = getattr(self, detector_attr, None)
            if detector is None:
                detector = StateChangeDetector(self)
                setattr(self, detector_attr, detector)
            return detector.call(method.__name__, *args, **kwargs)

        return wrapper

    return method_decorator


# ============== DEMONSTRATION ==============


def main():
    # Example 1: Basic usage
    print("=" * 60)
    print("EXAMPLE 1: Basic Object State Changes")
    print("=" * 60)

    class Person:
        def __init__(self, name, age):
            self.name = name
            self.age = age
            self.friends = []

        def have_birthday(self):
            self.age += 1

        def add_friend(self, friend):
            self.friends.append(friend)

        def change_name(self, new_name):
            old = self.name
            self.name = new_name
            return old

    person = Person("Alice", 30)
    detector = StateChangeDetector(person)

    result = detector.call("have_birthday")
    print(result)
    print()

    result = detector.call("add_friend", "Bob")
    print(result)
    print()

    # Example 2: Nested objects
    print("=" * 60)
    print("EXAMPLE 2: Nested Object Changes")
    print("=" * 60)

    class Address:
        def __init__(self, city, country):
            self.city = city
            self.country = country

    class Employee:
        def __init__(self, name):
            self.name = name
            self.address = Address("NYC", "USA")
            self.metadata = {"role": "developer", "level": 3}

        def relocate(self, city, country):
            self.address.city = city
            self.address.country = country

        def promote(self):
            self.metadata["level"] += 1

    emp = Employee("John")
    detector = StateChangeDetector(emp)

    result = detector.call("relocate", "London", "UK")
    print(result)
    print()

    result = detector.call("promote")
    print(result)
    print()

    # Example 3: Using context manager
    print("=" * 60)
    print("EXAMPLE 3: Context Manager Usage")
    print("=" * 60)

    class Counter:
        def __init__(self):
            self.value = 0
            self.history = []

        def increment(self, amount=1):
            self.history.append(self.value)
            self.value += amount

    counter = Counter()
    detector = StateChangeDetector(counter)

    with detector.track() as tracker:
        counter.increment(5)
        counter.increment(3)

    print(tracker)
    print()

    # Example 4: Wrapped proxy object
    print("=" * 60)
    print("EXAMPLE 4: Wrapped Proxy Object")
    print("=" * 60)

    class BankAccount:
        def __init__(self, balance=0):
            self.balance = balance
            self.transactions = []

        def deposit(self, amount):
            self.balance += amount
            self.transactions.append(f"+{amount}")

        def withdraw(self, amount):
            if amount > self.balance:
                raise ValueError("Insufficient funds")
            self.balance -= amount
            self.transactions.append(f"-{amount}")

    account = BankAccount(100)
    detector = StateChangeDetector(account)
    tracked_account = detector.wrap()

    tracked_account.deposit(50)
    tracked_account.withdraw(30)

    print("All tracked results:")
    for r in tracked_account.get_all_results():
        print(r)
        print()

    # Example 5: Slots-based class
    print("=" * 60)
    print("EXAMPLE 5: Slots-based Class")
    print("=" * 60)

    class Point:
        __slots__ = ["label", "x", "y"]

        def __init__(self, x, y):
            self.x = x
            self.y = y
            self.label = "origin" if x == 0 and y == 0 else "point"

        def move(self, dx, dy):
            self.x += dx
            self.y += dy
            self.label = "moved"

    point = Point(0, 0)
    detector = StateChangeDetector(point)

    result = detector.call("move", 5, 10)
    print(result)
    print()

    # Example 6: Set changes
    print("=" * 60)
    print("EXAMPLE 6: Set Changes")
    print("=" * 60)

    class TagManager:
        def __init__(self):
            self.tags = {"default"}

        def update_tags(self, add=None, remove=None):
            if add:
                self.tags.update(add)
            if remove:
                self.tags -= set(remove)

    tm = TagManager()
    detector = StateChangeDetector(tm)

    result = detector.call("update_tags", add={"python", "coding"}, remove=["default"])
    print(result)


if __name__ == "__main__":
    main()
