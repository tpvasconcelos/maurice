"""
Edge case tests for StateChangeDetector - testing limitations and boundary conditions.

These tests document scenarios where the detector may not catch state changes,
using pytest.mark.xfail to indicate expected limitations.

Run with: pytest test_state_change_detector_edge.py -v
"""

from __future__ import annotations

import contextvars
import functools
import os
import threading
import weakref
from unittest.mock import Mock

import pytest

from maurice.watchdog import (
    StateChangeDetector,
)

# ============== CLASS-LEVEL STATE TESTS ==============


class TestClassLevelState:
    """Tests for class-level state that is shared across instances."""

    @pytest.mark.xfail(reason="Class attributes are not tracked")
    def test_class_attribute_change_detected(self):
        """XFAIL: Class attribute changes should be detected."""

        class Example:
            class_var = 0

            def modify_class(self):
                Example.class_var += 1

        obj = Example()
        detector = StateChangeDetector(obj)
        before = Example.class_var
        result = detector.call("modify_class")
        after = Example.class_var

        assert after == before + 1  # Class var did change
        assert result.has_changes  # But detector should see it

    @pytest.mark.xfail(reason="Class method modifications not tracked")
    def test_class_method_addition_detected(self):
        """XFAIL: Adding methods to a class at runtime should be detected."""

        class Dynamic:
            def add_method(self):
                def new_method(self):
                    return "dynamic"

                type(self).new_method = new_method

        obj = Dynamic()
        detector = StateChangeDetector(obj)
        result = detector.call("add_method")

        assert hasattr(Dynamic, "new_method")
        assert result.has_changes

    @pytest.mark.xfail(reason="Class method deletion not tracked")
    def test_class_method_removal_detected(self):
        """XFAIL: Removing methods from a class should be detected."""

        class Shrinking:
            def to_remove(self):
                pass

            def remove_method(self):
                delattr(type(self), "to_remove")

        obj = Shrinking()
        detector = StateChangeDetector(obj)
        result = detector.call("remove_method")

        assert not hasattr(Shrinking, "to_remove")
        assert result.has_changes

    @pytest.mark.xfail(reason="Metaclass state not tracked")
    def test_metaclass_attribute_change_detected(self):
        """XFAIL: Metaclass attribute changes should be detected."""

        class Meta(type):
            registry = []

        class Registered(metaclass=Meta):
            def register(self):
                type(self).__class__.registry.append(self)

        obj = Registered()
        detector = StateChangeDetector(obj)
        before_len = len(Meta.registry)
        result = detector.call("register")
        after_len = len(Meta.registry)

        assert after_len == before_len + 1
        assert result.has_changes


# ============== DESCRIPTOR TESTS ==============


class TestDescriptors:
    """Tests for descriptor-based state management."""

    @pytest.mark.xfail(reason="Class-level descriptor modifications not tracked")
    def test_descriptor_modification_detected(self):
        """XFAIL: Modifying class descriptors should be detected."""

        class Validator:
            def __init__(self, max_val):
                self.max_val = max_val

            def __set_name__(self, owner, name):
                self.name = name

            def __get__(self, obj, objtype=None):
                return getattr(obj, f"_{self.name}", None)

            def __set__(self, obj, value):
                setattr(obj, f"_{self.name}", min(value, self.max_val))

        class Item:
            value = Validator(100)

            def __init__(self, val):
                self.value = val

            def change_max(self, new_max):
                type(self).value.max_val = new_max

        item = Item(50)
        detector = StateChangeDetector(item)
        result = detector.call("change_max", 200)

        assert Item.value.max_val == 200  # Descriptor did change
        assert result.has_changes

    @pytest.mark.xfail(reason="Descriptor internal state not tracked")
    def test_descriptor_internal_cache_detected(self):
        """XFAIL: Descriptor's internal caching state should be detected."""

        class CachedProperty:
            def __init__(self, func):
                self.func = func
                self.cache = {}

            def __get__(self, obj, objtype=None):
                if obj is None:
                    return self
                if id(obj) not in self.cache:
                    self.cache[id(obj)] = self.func(obj)
                return self.cache[id(obj)]

        class Expensive:
            @CachedProperty
            def computed(self):
                return 42

            def access_computed(self):
                return self.computed

        obj = Expensive()
        detector = StateChangeDetector(obj)
        result = detector.call("access_computed")

        # The descriptor's cache was populated
        assert id(obj) in Expensive.__dict__["computed"].cache
        assert result.has_changes


# ============== CLOSURE AND SCOPE TESTS ==============


class TestClosureState:
    """Tests for closure-captured state."""

    @pytest.mark.xfail(reason="Closure-captured state is invisible")
    def test_closure_state_detected(self):
        """XFAIL: State captured in closures should be detected."""

        def create_counter():
            count = [0]

            class Counter:
                def increment(self):
                    count[0] += 1

                def get(self):
                    return count[0]

            return Counter()

        counter = create_counter()
        detector = StateChangeDetector(counter)
        before = counter.get()
        result = detector.call("increment")
        after = counter.get()

        assert after == before + 1  # State did change
        assert result.has_changes  # But detector should see it

    @pytest.mark.xfail(reason="Nonlocal variable changes not tracked")
    def test_nonlocal_variable_detected(self):
        """XFAIL: Changes to nonlocal variables should be detected."""

        def make_accumulator():
            total = 0

            class Accumulator:
                def add(self, value):
                    nonlocal total
                    total += value

                def get_total(self):
                    return total

            return Accumulator()

        acc = make_accumulator()
        detector = StateChangeDetector(acc)
        before = acc.get_total()
        result = detector.call("add", 10)
        after = acc.get_total()

        assert after == before + 10
        assert result.has_changes

    @pytest.mark.xfail(reason="Factory-created shared state not tracked")
    def test_factory_shared_state_detected(self):
        """XFAIL: State shared via factory pattern should be detected."""

        def create_linked_objects():
            shared = {"value": 0}

            class ObjectA:
                def increment(self):
                    shared["value"] += 1

            class ObjectB:
                def get_value(self):
                    return shared["value"]

            return ObjectA(), ObjectB()

        obj_a, obj_b = create_linked_objects()
        detector = StateChangeDetector(obj_a)
        before = obj_b.get_value()
        result = detector.call("increment")
        after = obj_b.get_value()

        assert after == before + 1
        assert result.has_changes


# ============== GLOBAL AND MODULE STATE TESTS ==============


class TestGlobalState:
    """Tests for global and module-level state."""

    @pytest.mark.xfail(reason="Global state changes are not tracked")
    def test_global_state_change_detected(self):
        """XFAIL: Global state changes should be detected."""
        global_state = {"counter": 0}

        class Example:
            def modify_global(self):
                global_state["counter"] += 1

        obj = Example()
        detector = StateChangeDetector(obj)
        before = global_state["counter"]
        result = detector.call("modify_global")
        after = global_state["counter"]

        assert after == before + 1  # Global state did change
        assert result.has_changes  # But detector should see it

    @pytest.mark.xfail(reason="Module attribute changes not tracked")
    def test_module_attribute_change_detected(self):
        """XFAIL: Module attribute changes should be detected."""
        import types

        test_module = types.ModuleType("test_module")
        test_module.value = 0

        class ModuleModifier:
            def __init__(self, module):
                self.module = module

            def modify_module(self):
                self.module.value += 1

        obj = ModuleModifier(test_module)
        detector = StateChangeDetector(obj)
        before = test_module.value
        result = detector.call("modify_module")
        after = test_module.value

        assert after == before + 1
        assert result.has_changes

    @pytest.mark.xfail(reason="Environment variable changes not tracked")
    def test_environment_variable_change_detected(self):
        """XFAIL: Environment variable changes should be detected."""

        class EnvModifier:
            def set_env(self, key, value):
                os.environ[key] = value

        obj = EnvModifier()
        detector = StateChangeDetector(obj)
        result = detector.call("set_env", "_TEST_VAR_XYZ", "test_value")

        assert os.environ.get("_TEST_VAR_XYZ") == "test_value"
        assert result.has_changes

        # Cleanup
        del os.environ["_TEST_VAR_XYZ"]


# ============== WEAK REFERENCE TESTS ==============


class TestWeakReferences:
    """Tests for weakref-based relationships."""

    @pytest.mark.xfail(reason="WeakRef target state not tracked")
    def test_weakref_target_change_detected(self):
        """XFAIL: Changes to weakly-referenced objects should be detected."""

        class Target:
            def __init__(self):
                self.value = 0

        class Holder:
            def __init__(self, target):
                self.ref = weakref.ref(target)

            def modify_target(self):
                target = self.ref()
                if target:
                    target.value += 1

        target = Target()
        holder = Holder(target)
        detector = StateChangeDetector(holder)
        before = target.value
        result = detector.call("modify_target")
        after = target.value

        assert after == before + 1
        assert result.has_changes

    @pytest.mark.xfail(reason="WeakValueDictionary changes not fully tracked")
    def test_weakvaluedictionary_change_detected(self):
        """XFAIL: WeakValueDictionary state changes should be detected."""

        class Registry:
            def __init__(self):
                self.items = weakref.WeakValueDictionary()

            def register(self, key, obj):
                self.items[key] = obj

        class Item:
            pass

        registry = Registry()
        detector = StateChangeDetector(registry)
        item = Item()
        result = detector.call("register", "key1", item)

        assert "key1" in registry.items
        assert result.has_changes


# ============== CONTEXT VARIABLE TESTS ==============


class TestContextVariables:
    """Tests for contextvars-based state."""

    @pytest.mark.xfail(reason="Context variables are not tracked")
    def test_contextvar_change_detected(self):
        """XFAIL: Context variable changes should be detected."""
        request_id: contextvars.ContextVar[int] = contextvars.ContextVar("request_id", default=0)

        class RequestHandler:
            def set_request_id(self, req_id):
                request_id.set(req_id)

        handler = RequestHandler()
        detector = StateChangeDetector(handler)
        before = request_id.get()
        result = detector.call("set_request_id", 42)
        after = request_id.get()

        assert after == 42
        assert result.has_changes


# ============== THREAD-LOCAL STATE TESTS ==============


class TestThreadLocalState:
    """Tests for thread-local storage."""

    @pytest.mark.xfail(reason="Thread-local storage not tracked")
    def test_thread_local_change_detected(self):
        """XFAIL: Thread-local storage changes should be detected."""
        local_data = threading.local()

        class ThreadLocalModifier:
            def set_value(self, val):
                local_data.value = val

        obj = ThreadLocalModifier()
        detector = StateChangeDetector(obj)
        result = detector.call("set_value", "test")

        assert local_data.value == "test"
        assert result.has_changes


# ============== MEMOIZATION AND CACHING TESTS ==============


class TestMemoizationState:
    """Tests for memoization and caching patterns."""

    @pytest.mark.xfail(reason="functools.cache state not tracked")
    def test_functools_cache_detected(self):
        """XFAIL: functools.cache/lru_cache state should be detected."""

        class Calculator:
            def __init__(self):
                self.call_count = 0

            @functools.lru_cache(maxsize=128)
            def expensive(self, n):
                self.call_count += 1  # This IS tracked
                return n * 2

            def compute(self, n):
                return self.expensive(n)

        calc = Calculator()
        detector = StateChangeDetector(calc)

        # First call - populates cache
        result1 = detector.call("compute", 5)
        cache_info_1 = calc.expensive.cache_info()

        # Second call - uses cache
        result2 = detector.call("compute", 5)
        cache_info_2 = calc.expensive.cache_info()

        # Cache hits increased but detector doesn't see it
        assert cache_info_2.hits > cache_info_1.hits
        assert result2.has_changes  # Should detect cache state change


# ============== SINGLETON AND REGISTRY PATTERNS ==============


class TestSingletonState:
    """Tests for singleton and registry patterns."""

    @pytest.mark.xfail(reason="Singleton instance state not tracked through class")
    def test_singleton_state_change_detected(self):
        """XFAIL: Singleton pattern state changes should be detected."""

        class Singleton:
            _instance = None
            _value = 0

            def __new__(cls):
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                return cls._instance

            def increment(self):
                Singleton._value += 1

            @classmethod
            def get_value(cls):
                return cls._value

        obj = Singleton()
        detector = StateChangeDetector(obj)
        before = Singleton.get_value()
        result = detector.call("increment")
        after = Singleton.get_value()

        assert after == before + 1
        assert result.has_changes

    @pytest.mark.xfail(reason="Class-level registry not tracked")
    def test_registry_pattern_detected(self):
        """XFAIL: Registry pattern state changes should be detected."""

        class Plugin:
            _registry = {}

            def __init__(self, name):
                self.name = name

            def register(self):
                Plugin._registry[self.name] = self

        plugin = Plugin("test_plugin")
        detector = StateChangeDetector(plugin)
        result = detector.call("register")

        assert "test_plugin" in Plugin._registry
        assert result.has_changes


# ============== MUTABLE DEFAULT ARGUMENT TESTS ==============


class TestMutableDefaults:
    """Tests for mutable default argument anti-pattern."""

    @pytest.mark.xfail(reason="Mutable default arguments not tracked")
    def test_mutable_default_change_detected(self):
        """XFAIL: Changes to mutable default arguments should be detected."""

        class Collector:
            def collect(self, item, items=[]):  # noqa: B006 - intentional
                items.append(item)
                return items

        obj = Collector()
        detector = StateChangeDetector(obj)

        result1 = detector.call("collect", "a")
        result2 = detector.call("collect", "b")

        # The default list has been mutated
        assert result2.return_value == ["a", "b"]
        assert result2.has_changes  # Should detect the default arg mutation


# ============== OBJECT IDENTITY CHANGES ==============


class TestIdentityChanges:
    """Tests for object identity and class changes."""

    @pytest.mark.xfail(reason="__class__ reassignment not tracked")
    def test_class_reassignment_detected(self):
        """XFAIL: Changing an object's __class__ should be detected."""

        class Original:
            def transform(self):
                self.__class__ = Transformed

        class Transformed:
            pass

        obj = Original()
        detector = StateChangeDetector(obj)
        result = detector.call("transform")

        assert type(obj).__name__ == "Transformed"
        assert result.has_changes

    @pytest.mark.xfail(reason="Dynamic base class modification not tracked")
    def test_dynamic_base_modification_detected(self):
        """XFAIL: Modifying base class should be detected."""

        class Base:
            base_value = 1

        class Derived(Base):
            def modify_base(self):
                Base.base_value = 100

        obj = Derived()
        detector = StateChangeDetector(obj)
        before = Base.base_value
        result = detector.call("modify_base")
        after = Base.base_value

        assert after == 100
        assert result.has_changes


# ============== GENERATOR AND ITERATOR STATE ==============


class TestGeneratorState:
    """Tests for generator and iterator internal state."""

    @pytest.mark.xfail(reason="Generator internal state not tracked")
    def test_generator_state_detected(self):
        """XFAIL: Generator internal state changes should be detected."""

        class GeneratorHolder:
            def __init__(self):
                self.gen = self._make_gen()

            def _make_gen(self):
                yield 1
                yield 2
                yield 3

            def advance(self):
                return next(self.gen)

        holder = GeneratorHolder()
        detector = StateChangeDetector(holder)
        result = detector.call("advance")

        # Generator advanced but detector might not see internal state change
        assert result.return_value == 1
        assert result.has_changes

    @pytest.mark.xfail(reason="False positives on iterator state")
    def test_iterator_state_false_positive(self):
        class IteratorHolder:
            def __init__(self):
                self.iter = iter(range(10))

            def noop(self):
                pass

        counter = IteratorHolder()
        detector = StateChangeDetector(counter)
        result = detector.call("noop")
        assert not result.has_changes

    @pytest.mark.xfail(reason="False positives on Mock state")
    def test_mock_state_false_positive(self):
        class ServiceClient:
            def __init__(self, mock):
                self.mock = mock

            def noop(self):
                pass

        client = ServiceClient(Mock())
        detector = StateChangeDetector(client)
        result = detector.call("noop")

        assert not result.has_changes


# ============== EXTERNAL RESOURCE STATE ==============


class TestExternalResources:
    """Tests for external resource state changes."""

    @pytest.mark.xfail(reason="File system state not tracked")
    def test_file_system_change_detected(self):
        """XFAIL: File system changes should be detected."""
        import tempfile

        class FileWriter:
            def __init__(self, path):
                self.path = path

            def write(self, content):
                with open(self.path, "w") as f:
                    f.write(content)

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            path = f.name

        try:
            writer = FileWriter(path)
            detector = StateChangeDetector(writer)
            result = detector.call("write", "test content")

            with open(path) as f:
                assert f.read() == "test content"
            assert result.has_changes
        finally:
            os.unlink(path)


# ============== OBSERVER PATTERN STATE ==============


class TestObserverPattern:
    """Tests for observer/subscriber patterns."""

    @pytest.mark.xfail(reason="Observer state changes not tracked")
    def test_observer_notification_detected(self):
        """XFAIL: State changes in observers should be detected."""

        class Observer:
            def __init__(self):
                self.notifications = []

            def notify(self, message):
                self.notifications.append(message)

        class Subject:
            def __init__(self):
                self.observers = []

            def add_observer(self, obs):
                self.observers.append(obs)

            def notify_all(self, message):
                for obs in self.observers:
                    obs.notify(message)

        observer = Observer()
        subject = Subject()
        subject.add_observer(observer)

        detector = StateChangeDetector(subject)
        result = detector.call("notify_all", "test message")

        assert "test message" in observer.notifications
        assert result.has_changes  # Should detect observer state change


# ============== LAZY LOADING STATE ==============


class TestLazyLoading:
    """Tests for lazy-loaded attributes."""

    @pytest.mark.xfail(reason="__getattr__ side effects may not be tracked properly")
    def test_getattr_lazy_load_detected(self):
        """XFAIL: Lazy loading via __getattr__ side effects should be detected."""

        class LazyLoader:
            def __init__(self):
                self._cache = {}

            def __getattr__(self, name):
                if name.startswith("_"):
                    raise AttributeError(name)
                if name not in self._cache:
                    self._cache[name] = f"loaded_{name}"
                return self._cache[name]

            def access(self, name):
                return getattr(self, name)

        obj = LazyLoader()
        detector = StateChangeDetector(obj)
        result = detector.call("access", "test_attr")

        assert result.return_value == "loaded_test_attr"
        assert "test_attr" in obj._cache
        assert result.has_changes


# ============== SLOT INHERITANCE TESTS ==============


class TestSlotInheritance:
    """Tests for complex slot inheritance scenarios."""

    @pytest.mark.xfail(reason="Multiple inheritance with slots may have edge cases")
    def test_diamond_inheritance_slots_detected(self):
        """XFAIL: Diamond inheritance with slots should be fully tracked."""

        class A:
            __slots__ = ["a"]

            def __init__(self):
                self.a = 1

        class B(A):
            __slots__ = ["b"]

            def __init__(self):
                super().__init__()
                self.b = 2

        class C(A):
            __slots__ = ["c"]

            def __init__(self):
                super().__init__()
                self.c = 3

        class D(B, C):
            __slots__ = ["d"]

            def __init__(self):
                super().__init__()
                self.d = 4

            def modify_all(self):
                self.a = 10
                self.b = 20
                self.c = 30
                self.d = 40

        obj = D()
        detector = StateChangeDetector(obj)
        result = detector.call("modify_all")

        assert result.has_changes
        assert len(result.modified) == 4  # All four slots should be tracked


# ============== ASYNC STATE TESTS ==============


class TestAsyncState:
    """Tests for async-related state (sync wrapper tests)."""

    @pytest.mark.xfail(reason="Coroutine internal state not tracked")
    def test_coroutine_state_detected(self):
        """XFAIL: Coroutine objects internal state should be detected."""

        class AsyncHolder:
            def __init__(self):
                self.coro = None

            def create_coro(self):
                async def my_coro():
                    return 42

                self.coro = my_coro()

        holder = AsyncHolder()
        detector = StateChangeDetector(holder)
        result = detector.call("create_coro")

        # Coroutine created but internal state is opaque
        assert holder.coro is not None
        assert result.has_changes


# ============== SPECIAL METHOD SIDE EFFECTS ==============


class TestSpecialMethodSideEffects:
    """Tests for side effects in special methods."""

    @pytest.mark.xfail(reason="Side effects in __repr__ not tracked")
    def test_repr_side_effect_detected(self):
        """XFAIL: Side effects in __repr__ during comparison should be detected."""

        class SneakyRepr:
            call_count = 0

            def __init__(self):
                self.value = 0

            def __repr__(self):
                SneakyRepr.call_count += 1
                return f"Sneaky({self.value})"

            def do_nothing(self):
                pass

        obj = SneakyRepr()
        detector = StateChangeDetector(obj)
        before = SneakyRepr.call_count
        result = detector.call("do_nothing")
        after = SneakyRepr.call_count

        # __repr__ may be called during snapshot/comparison
        if after > before:
            assert result.has_changes  # Should track class-level side effect

    @pytest.mark.xfail(reason="Side effects in __hash__ not tracked")
    def test_hash_side_effect_detected(self):
        """XFAIL: Side effects in __hash__ should be detected."""

        class SneakyHash:
            call_count = 0

            def __hash__(self):
                SneakyHash.call_count += 1
                return id(self)

            def trigger_hash(self):
                {self}  # Creates a set, calling __hash__

        obj = SneakyHash()
        detector = StateChangeDetector(obj)
        before = SneakyHash.call_count
        result = detector.call("trigger_hash")
        after = SneakyHash.call_count

        assert after > before
        assert result.has_changes


# ============== REFERENCE CYCLE WITH STATE ==============


class TestReferenceCyclesWithState:
    """Tests for circular references that include state changes."""

    def test_mutual_reference_state_change(self):
        """Test that mutual references with state changes are handled."""

        class Node:
            def __init__(self, name):
                self.name = name
                self.partner = None
                self.value = 0

            def set_partner(self, other):
                self.partner = other
                other.partner = self

            def increment_both(self):
                self.value += 1
                if self.partner:
                    self.partner.value += 1

        a = Node("A")
        b = Node("B")
        a.set_partner(b)

        detector = StateChangeDetector(a)
        result = detector.call("increment_both")

        # At minimum, self.value change should be detected
        assert result.has_changes
        # Partner's change may or may not be detected depending on implementation


# ============== PARAMETRIZED LIMITATION TESTS ==============


class TestParametrizedLimitations:
    """Parametrized tests exploring various limitations."""

    @pytest.mark.parametrize(
        "storage_type,getter,setter",
        [
            pytest.param(
                "class_attr",
                lambda cls: cls.class_val,
                lambda cls, v: setattr(cls, "class_val", v),
                marks=pytest.mark.xfail(reason="Class attributes not tracked"),
            ),
            pytest.param(
                "global_dict",
                lambda _: TestParametrizedLimitations._global.get("val", 0),
                lambda _, v: TestParametrizedLimitations._global.update({"val": v}),
                marks=pytest.mark.xfail(reason="Global state not tracked"),
            ),
        ],
    )
    def test_external_storage_detection(self, storage_type, getter, setter):
        """XFAIL: Various external storage mechanisms should be detected."""
        TestParametrizedLimitations._global = {}

        class Example:
            class_val = 0

            def modify(self):
                if storage_type == "class_attr":
                    Example.class_val += 1
                else:
                    setter(None, getter(None) + 1)

        obj = Example()
        detector = StateChangeDetector(obj)
        result = detector.call("modify")

        assert result.has_changes
