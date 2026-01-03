"""
Comprehensive test suite for StateChangeDetector.

Run with: pytest test_state_change_detector.py -v
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import pytest

from maurice.watchdog import (
    AttributeChange,
    ChangeType,
    StateChangeDetector,
    StateChangeResult,
    _UncopyableMarker,
)

# ============== FIXTURES ==============


@pytest.fixture
def simple_object():
    """A simple object with basic attributes."""

    class Simple:
        def __init__(self):
            self.value = 0
            self.name = "initial"

        def set_value(self, v):
            self.value = v

        def set_name(self, n):
            self.name = n

        def increment(self):
            self.value += 1

        def no_change(self):
            pass

        def raises_error(self):
            self.value = 999
            raise ValueError("Intentional error")

    return Simple()


@pytest.fixture
def nested_object():
    """An object with nested objects."""

    class Inner:
        def __init__(self):
            self.x = 1
            self.y = 2

    class Outer:
        def __init__(self):
            self.inner = Inner()
            self.data = {"key": "value"}

        def modify_inner(self):
            self.inner.x = 100

        def modify_dict(self):
            self.data["key"] = "modified"
            self.data["new_key"] = "new_value"

    return Outer()


@pytest.fixture
def collection_object():
    """An object with various collections."""

    class WithCollections:
        def __init__(self):
            self.items: list[int] = [1, 2, 3]
            self.mapping = {"a": 1, "b": 2}
            self.tags = {"tag1", "tag2"}

        def append_item(self, item):
            self.items.append(item)

        def remove_item(self, item):
            self.items.remove(item)

        def modify_item(self, idx, value):
            self.items[idx] = value

        def add_mapping(self, key, value):
            self.mapping[key] = value

        def remove_mapping(self, key):
            del self.mapping[key]

        def add_tag(self, tag):
            self.tags.add(tag)

        def remove_tag(self, tag):
            self.tags.discard(tag)

    return WithCollections()


@pytest.fixture
def slots_object():
    """An object using __slots__."""

    class WithSlots:
        __slots__ = ["x", "y", "z"]

        def __init__(self):
            self.x = 0
            self.y = 0
            # z intentionally not initialized

        def set_x(self, val):
            self.x = val

        def init_z(self, val):
            self.z = val

    return WithSlots()


@pytest.fixture
def detector(simple_object):
    """Default detector with simple object."""
    return StateChangeDetector(simple_object)


# ============== BASIC FUNCTIONALITY TESTS ==============


class TestBasicDetection:
    """Tests for basic state change detection."""

    def test_detects_attribute_modification(self, simple_object):
        detector = StateChangeDetector(simple_object)
        result = detector.call("set_value", 42)

        assert result.has_changes
        assert len(result.modified) == 1
        assert result.modified[0].name == "value"
        assert result.modified[0].old_value == 0
        assert result.modified[0].new_value == 42

    def test_detects_no_change(self, simple_object):
        detector = StateChangeDetector(simple_object)
        result = detector.call("no_change")

        assert not result.has_changes
        assert len(result.changes) == 0

    def test_detects_attribute_addition(self):
        class Dynamic:
            def __init__(self):
                self.existing = 1

            def add_attr(self):
                self.new_attr = "added"

        obj = Dynamic()
        detector = StateChangeDetector(obj)
        result = detector.call("add_attr")

        assert result.has_changes
        assert len(result.added) == 1
        assert result.added[0].name == "new_attr"
        assert result.added[0].new_value == "added"

    def test_detects_attribute_removal(self):
        class Dynamic:
            def __init__(self):
                self.to_remove = "will be removed"

            def remove_attr(self):
                del self.to_remove

        obj = Dynamic()
        detector = StateChangeDetector(obj)
        result = detector.call("remove_attr")

        assert result.has_changes
        assert len(result.removed) == 1
        assert result.removed[0].name == "to_remove"
        assert result.removed[0].old_value == "will be removed"

    def test_detects_multiple_changes(self, simple_object):
        class Multi:
            def __init__(self):
                self.a = 1
                self.b = 2

            def change_both(self):
                self.a = 10
                self.b = 20

        obj = Multi()
        detector = StateChangeDetector(obj)
        result = detector.call("change_both")

        assert result.has_changes
        assert len(result.modified) == 2
        changed_names = {c.name for c in result.modified}
        assert changed_names == {"a", "b"}

    def test_captures_return_value(self, simple_object):
        class WithReturn:
            def __init__(self):
                self.value = 0

            def compute(self):
                self.value = 42
                return "computed"

        obj = WithReturn()
        detector = StateChangeDetector(obj)
        result = detector.call("compute")

        assert result.return_value == "computed"

    def test_method_name_recorded(self, simple_object):
        detector = StateChangeDetector(simple_object)
        result = detector.call("increment")

        assert result.method_name == "increment"


# ============== EXCEPTION HANDLING TESTS ==============


class TestExceptionHandling:
    """Tests for handling exceptions during method calls."""

    def test_captures_exception(self, simple_object):
        detector = StateChangeDetector(simple_object)
        result = detector.call("raises_error")

        assert result.exception_raised is not None
        assert isinstance(result.exception_raised, ValueError)
        assert str(result.exception_raised) == "Intentional error"

    def test_detects_changes_before_exception(self, simple_object):
        detector = StateChangeDetector(simple_object)
        result = detector.call("raises_error")

        # Should detect the change that happened before the exception
        assert result.has_changes
        assert any(c.new_value == 999 for c in result.modified)

    def test_non_callable_raises_type_error(self, simple_object):
        detector = StateChangeDetector(simple_object)

        with pytest.raises(TypeError, match="not callable"):
            detector.call("value")  # 'value' is an attribute, not a method


# ============== NESTED OBJECT TESTS ==============


class TestNestedObjects:
    """Tests for nested object change detection."""

    def test_detects_nested_attribute_change(self, nested_object):
        detector = StateChangeDetector(nested_object)
        result = detector.call("modify_inner")

        assert result.has_changes
        # Should detect the change in inner.x
        paths = [c.path for c in result.changes]
        assert any("inner" in p and "x" in p for p in paths)

    def test_detects_nested_dict_modification(self, nested_object):
        detector = StateChangeDetector(nested_object)
        result = detector.call("modify_dict")

        assert result.has_changes
        # Should detect both the modification and the addition
        assert len(result.changes) >= 2

    def test_respects_max_depth(self):
        class DeepNested:
            def __init__(self, depth=0, max_depth=5):
                self.value = depth
                if depth < max_depth:
                    self.child = DeepNested(depth + 1, max_depth)

            def modify_deep(self):
                current = self
                while hasattr(current, "child"):
                    current = current.child
                current.value = 999

        obj = DeepNested()
        detector = StateChangeDetector(obj, max_depth=2)
        result = detector.call("modify_deep")

        # Should not cause infinite recursion or stack overflow
        assert isinstance(result, StateChangeResult)


# ============== COLLECTION TESTS ==============


class TestCollectionChanges:
    """Tests for collection change detection."""

    def test_detects_list_append(self, collection_object):
        detector = StateChangeDetector(collection_object)
        result = detector.call("append_item", 4)

        assert result.has_changes
        # Should detect length change and new item
        assert any(c.change_type == ChangeType.ADDED for c in result.changes)

    def test_detects_list_remove(self, collection_object):
        detector = StateChangeDetector(collection_object)
        result = detector.call("remove_item", 2)

        assert result.has_changes

    def test_detects_list_modification(self, collection_object):
        detector = StateChangeDetector(collection_object)
        result = detector.call("modify_item", 0, 100)

        assert result.has_changes
        assert any(c.change_type == ChangeType.MODIFIED for c in result.changes)

    def test_detects_dict_addition(self, collection_object):
        detector = StateChangeDetector(collection_object)
        result = detector.call("add_mapping", "c", 3)

        assert result.has_changes
        assert any(c.change_type == ChangeType.ADDED for c in result.changes)

    def test_detects_dict_removal(self, collection_object):
        detector = StateChangeDetector(collection_object)
        result = detector.call("remove_mapping", "a")

        assert result.has_changes
        assert any(c.change_type == ChangeType.REMOVED for c in result.changes)

    def test_detects_set_addition(self, collection_object):
        detector = StateChangeDetector(collection_object)
        result = detector.call("add_tag", "tag3")

        assert result.has_changes
        assert any(c.change_type == ChangeType.ADDED for c in result.changes)

    def test_detects_set_removal(self, collection_object):
        detector = StateChangeDetector(collection_object)
        result = detector.call("remove_tag", "tag1")

        assert result.has_changes
        assert any(c.change_type == ChangeType.REMOVED for c in result.changes)

    def test_collection_tracking_can_be_disabled(self, collection_object):
        detector = StateChangeDetector(collection_object, track_collections=False)
        result = detector.call("append_item", 4)

        # Still detects change but not at granular level
        assert result.has_changes


# ============== SLOTS TESTS ==============


class TestSlotsSupport:
    """Tests for __slots__-based classes."""

    def test_detects_slot_modification(self, slots_object):
        detector = StateChangeDetector(slots_object)
        result = detector.call("set_x", 100)

        assert result.has_changes
        assert result.modified[0].name == "x"
        assert result.modified[0].old_value == 0
        assert result.modified[0].new_value == 100

    def test_detects_slot_initialization(self, slots_object):
        detector = StateChangeDetector(slots_object)
        result = detector.call("init_z", 50)

        assert result.has_changes
        assert any(c.name == "z" and c.change_type == ChangeType.ADDED for c in result.changes)

    def test_handles_mixed_slots_and_dict(self):
        class MixedSlots:
            __slots__ = ["__dict__", "slot_attr"]

            def __init__(self):
                self.slot_attr = 1
                self.dict_attr = 2

            def modify_both(self):
                self.slot_attr = 10
                self.dict_attr = 20

        obj = MixedSlots()
        detector = StateChangeDetector(obj)
        result = detector.call("modify_both")

        assert result.has_changes
        assert len(result.modified) == 2


# ============== CONTEXT MANAGER TESTS ==============


class TestContextManager:
    """Tests for context manager usage."""

    def test_tracks_changes_in_context(self, simple_object):
        detector = StateChangeDetector(simple_object)

        with detector.track() as tracker:
            simple_object.value = 100
            simple_object.name = "changed"

        assert tracker.has_changes
        assert len(tracker.modified) == 2

    def test_tracks_multiple_operations(self, simple_object):
        detector = StateChangeDetector(simple_object)

        with detector.track() as tracker:
            simple_object.increment()
            simple_object.increment()
            simple_object.increment()

        assert tracker.has_changes
        # Should see net change from 0 to 3
        value_change = next(c for c in tracker.modified if c.name == "value")
        assert value_change.old_value == 0
        assert value_change.new_value == 3

    def test_propagates_exception(self, simple_object):
        detector = StateChangeDetector(simple_object)

        with pytest.raises(RuntimeError, match="test error"), detector.track() as tracker:
            simple_object.value = 50
            raise RuntimeError("test error")

        # Should still track changes before exception
        assert tracker.has_changes

    def test_records_exception_in_result(self, simple_object):
        detector = StateChangeDetector(simple_object)

        try:
            with detector.track() as tracker:
                raise ValueError("tracked error")
        except ValueError:
            pass

        assert tracker.exception_raised is not None
        assert isinstance(tracker.exception_raised, ValueError)


# ============== PROXY WRAPPER TESTS ==============


class TestTrackedObjectProxy:
    """Tests for the proxy wrapper."""

    def test_proxy_forwards_method_calls(self, simple_object):
        detector = StateChangeDetector(simple_object)
        proxy = detector.wrap()

        proxy.set_value(42)

        assert simple_object.value == 42

    def test_proxy_tracks_all_calls(self, simple_object):
        detector = StateChangeDetector(simple_object)
        proxy = detector.wrap()

        proxy.increment()
        proxy.increment()
        proxy.set_name("new")

        results = proxy.get_all_results()
        assert len(results) == 3

    def test_proxy_attribute_access(self, simple_object):
        detector = StateChangeDetector(simple_object)
        proxy = detector.wrap()

        assert proxy.value == 0
        assert proxy.name == "initial"

    def test_proxy_attribute_setting(self, simple_object):
        detector = StateChangeDetector(simple_object)
        proxy = detector.wrap()

        proxy.value = 999

        assert simple_object.value == 999

    def test_proxy_unwrap(self, simple_object):
        detector = StateChangeDetector(simple_object)
        proxy = detector.wrap()

        unwrapped = proxy.get_unwrapped()

        assert unwrapped is simple_object

    def test_proxy_reraises_exceptions(self, simple_object):
        detector = StateChangeDetector(simple_object)
        proxy = detector.wrap()

        with pytest.raises(ValueError, match="Intentional error"):
            proxy.raises_error()


# ============== CONFIGURATION TESTS ==============


class TestConfiguration:
    """Tests for detector configuration options."""

    def test_ignore_private_attributes(self):
        class WithPrivate:
            def __init__(self):
                self.public = 1
                self._private = 2

            def modify(self):
                self.public = 10
                self._private = 20

        obj = WithPrivate()
        detector = StateChangeDetector(obj, ignore_private=True)
        result = detector.call("modify")

        assert len(result.modified) == 1
        assert result.modified[0].name == "public"

    def test_ignore_dunder_attributes(self):
        class WithDunder:
            def __init__(self):
                self.normal = 1

            def modify(self):
                self.normal = 10
                self.__dict__["__custom__"] = "value"

        obj = WithDunder()
        detector = StateChangeDetector(obj, ignore_dunder=True)
        result = detector.call("modify")

        # Should not include __custom__ in changes
        assert all(not c.name.startswith("__") for c in result.changes)

    def test_shallow_comparison(self):
        class WithNested:
            def __init__(self):
                self.nested = {"key": [1, 2, 3]}

            def modify_nested(self):
                self.nested["key"].append(4)

        obj = WithNested()
        detector = StateChangeDetector(obj, deep=False)
        result = detector.call("modify_nested")

        # With shallow comparison, might not detect nested changes
        # depending on implementation details
        assert isinstance(result, StateChangeResult)


# ============== EDGE CASES ==============


class TestEdgeCases:
    """Tests for edge cases and unusual scenarios."""

    def test_circular_reference(self):
        class Circular:
            def __init__(self):
                self.value = 0
                self.ref = None

            def create_cycle(self):
                self.ref = self
                self.value = 42

        obj = Circular()
        detector = StateChangeDetector(obj)
        result = detector.call("create_cycle")

        # Should not cause infinite recursion
        assert result.has_changes

    def test_uncopyable_object(self):
        class WithUncopyable:
            def __init__(self):
                self.lock = threading.Lock()
                self.value = 0

            def modify(self):
                self.value = 42

        obj = WithUncopyable()
        detector = StateChangeDetector(obj)
        result = detector.call("modify")

        # Should handle uncopyable lock gracefully
        assert result.has_changes
        value_change = next(c for c in result.modified if c.name == "value")
        assert value_change.new_value == 42

    def test_object_with_broken_eq(self):
        class BrokenEq:
            def __init__(self):
                self.value = 0

            def __eq__(self, other):
                raise RuntimeError("Comparison not allowed")

            def modify(self):
                self.value = 42

        class Container:
            def __init__(self):
                self.broken = BrokenEq()

            def do_modify(self):
                self.broken.modify()

        obj = Container()
        detector = StateChangeDetector(obj)
        # Should not crash
        result = detector.call("do_modify")
        assert isinstance(result, StateChangeResult)

    def test_none_values(self):
        class WithNone:
            def __init__(self):
                self.value = None

            def set_value(self):
                self.value = "not none"

            def unset_value(self):
                self.value = None

        obj = WithNone()
        detector = StateChangeDetector(obj)

        result1 = detector.call("set_value")
        assert result1.has_changes
        assert result1.modified[0].old_value is None

        result2 = detector.call("unset_value")
        assert result2.has_changes
        assert result2.modified[0].new_value is None

    def test_type_change(self):
        class TypeChanger:
            def __init__(self):
                self.value = 42

            def change_type(self):
                self.value = "now a string"

        obj = TypeChanger()
        detector = StateChangeDetector(obj)
        result = detector.call("change_type")

        assert result.has_changes
        change = result.modified[0]
        assert change.old_value == 42
        assert change.new_value == "now a string"

    def test_empty_object(self):
        class Empty:
            def do_nothing(self):
                pass

        obj = Empty()
        detector = StateChangeDetector(obj)
        result = detector.call("do_nothing")

        assert not result.has_changes

    def test_property_access(self):
        class WithProperty:
            def __init__(self):
                self._value = 0

            @property
            def value(self):
                return self._value

            def modify(self):
                self._value = 100

        obj = WithProperty()
        detector = StateChangeDetector(obj)
        result = detector.call("modify")

        # Should detect change in _value
        assert result.has_changes

    def test_dataclass_object(self):
        @dataclass
        class DataClassObj:
            x: int = 0
            y: str = "hello"

            def modify(self):
                self.x = 100
                self.y = "world"

        obj = DataClassObj()
        detector = StateChangeDetector(obj)
        result = detector.call("modify")

        assert result.has_changes
        assert len(result.modified) == 2


# ============== LAST RESULT TESTS ==============


class TestLastResult:
    """Tests for last_result property."""

    def test_last_result_updated(self, simple_object):
        detector = StateChangeDetector(simple_object)

        detector.call("increment")
        result1 = detector.last_result

        detector.call("set_name", "new")
        result2 = detector.last_result

        assert result1.method_name == "increment"
        assert result2.method_name == "set_name"
        assert result1 is not result2

    def test_last_result_none_initially(self, simple_object):
        detector = StateChangeDetector(simple_object)
        assert detector.last_result is None


# ============== ATTRIBUTE CHANGE REPRESENTATION ==============


class TestAttributeChangeRepr:
    """Tests for AttributeChange string representation."""

    def test_added_repr(self):
        change = AttributeChange(
            name="new_attr", change_type=ChangeType.ADDED, new_value=42, path="obj.new_attr"
        )
        repr_str = repr(change)
        assert "ADDED" in repr_str
        assert "42" in repr_str

    def test_removed_repr(self):
        change = AttributeChange(
            name="old_attr", change_type=ChangeType.REMOVED, old_value="gone", path="obj.old_attr"
        )
        repr_str = repr(change)
        assert "REMOVED" in repr_str
        assert "gone" in repr_str

    def test_modified_repr(self):
        change = AttributeChange(
            name="attr", change_type=ChangeType.MODIFIED, old_value=1, new_value=2, path="obj.attr"
        )
        repr_str = repr(change)
        assert "MODIFIED" in repr_str
        assert "1" in repr_str
        assert "2" in repr_str


# ============== STATE CHANGE RESULT TESTS ==============


class TestStateChangeResult:
    """Tests for StateChangeResult class."""

    def test_has_changes_true(self):
        result = StateChangeResult(method_name="test")
        result.changes = [AttributeChange("x", ChangeType.MODIFIED, 1, 2)]
        assert result.has_changes

    def test_has_changes_false(self):
        result = StateChangeResult(method_name="test")
        assert not result.has_changes

    def test_filtered_properties(self):
        result = StateChangeResult(method_name="test")
        result.changes = [
            AttributeChange("a", ChangeType.ADDED, new_value=1),
            AttributeChange("r", ChangeType.REMOVED, old_value=2),
            AttributeChange("m", ChangeType.MODIFIED, 3, 4),
        ]

        assert len(result.added) == 1
        assert len(result.removed) == 1
        assert len(result.modified) == 1

    def test_repr_format(self):
        result = StateChangeResult(method_name="test_method")
        result.changes = [AttributeChange("x", ChangeType.MODIFIED, 1, 2, "obj.x")]
        repr_str = repr(result)

        assert "test_method" in repr_str
        assert "1" in repr_str


# ============== UNCOPYABLE MARKER TESTS ==============


class TestUncopyableMarker:
    """Tests for _UncopyableMarker class."""

    def test_marker_equality(self):
        marker1 = _UncopyableMarker("Lock", 12345)
        marker2 = _UncopyableMarker("Lock", 12345)
        marker3 = _UncopyableMarker("Lock", 99999)

        assert marker1 == marker2
        assert marker1 != marker3

    def test_marker_repr(self):
        marker = _UncopyableMarker("threading.Lock", 12345)
        repr_str = repr(marker)

        assert "Uncopyable" in repr_str
        assert "threading.Lock" in repr_str


# ============== INTEGRATION TESTS ==============


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_complex_workflow(self):
        class ComplexObject:
            def __init__(self):
                self.users = []
                self.settings = {"theme": "dark"}
                self.counter = 0

            def add_user(self, name):
                self.users.append({"name": name, "id": self.counter})
                self.counter += 1

            def update_settings(self, **kwargs):
                self.settings.update(kwargs)

            def reset(self):
                self.users.clear()
                self.settings = {"theme": "light"}
                self.counter = 0

        obj = ComplexObject()
        detector = StateChangeDetector(obj)
        wrapped = detector.wrap()

        wrapped.add_user("Alice")
        wrapped.add_user("Bob")
        wrapped.update_settings(theme="light", language="en")
        wrapped.reset()

        results = wrapped.get_all_results()
        assert len(results) == 4
        assert all(r.has_changes for r in results)

    def test_inheritance_chain(self):
        class Base:
            def __init__(self):
                self.base_attr = "base"

            def base_method(self):
                self.base_attr = "modified"

        class Middle(Base):
            def __init__(self):
                super().__init__()
                self.middle_attr = "middle"

        class Derived(Middle):
            def __init__(self):
                super().__init__()
                self.derived_attr = "derived"

            def modify_all(self):
                self.base_attr = "new_base"
                self.middle_attr = "new_middle"
                self.derived_attr = "new_derived"

        obj = Derived()
        detector = StateChangeDetector(obj)
        result = detector.call("modify_all")

        assert result.has_changes
        assert len(result.modified) == 3


# ============== PARAMETRIZED TESTS ==============


class TestParametrized:
    """Parametrized tests for various scenarios."""

    @pytest.mark.parametrize(
        "old_val,new_val",
        [
            (0, 1),
            ("a", "b"),
            (True, False),
            (1.0, 2.0),
            (None, "value"),
            ([], [1]),
            ({}, {"a": 1}),
        ],
    )
    def test_various_type_changes(self, old_val, new_val):
        class Obj:
            def __init__(self):
                self.value = old_val

            def change(self):
                self.value = new_val

        obj = Obj()
        detector = StateChangeDetector(obj)
        result = detector.call("change")

        assert result.has_changes

    @pytest.mark.parametrize(
        "collection_type,initial,operation,expected_change_type",
        [
            (list, [1, 2], lambda x: x.append(3), ChangeType.ADDED),
            (set, {1, 2}, lambda x: x.add(3), ChangeType.ADDED),
            (dict, {"a": 1}, lambda x: x.update({"b": 2}), ChangeType.ADDED),
        ],
    )
    def test_collection_additions(self, collection_type, initial, operation, expected_change_type):
        class Obj:
            def __init__(self):
                self.data = collection_type(initial)

            def modify(self):
                operation(self.data)

        obj = Obj()
        detector = StateChangeDetector(obj)
        result = detector.call("modify")

        assert result.has_changes
        assert any(c.change_type == expected_change_type for c in result.changes)
