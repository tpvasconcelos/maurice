# Todos

### Method Caching

## Features
-
- Make method caching work for async methods
- Make method caching work for weakref'ed attributes?
- Make method caching work changes in the class global state that might affect the method output

    ```python
    @pytest.mark.xfail(reason="Class attributes are not tracked")
    def test_class_attribute_change_detected(self):
        """XFAIL: Class attribute changes should be detected."""
        class Example:
            class_var = 0
            def __init__(self):
                pass
            def modify_class(self):
                Example.class_var += 1

        obj = Example()
        detector = StateChangeDetector(obj)

        before = Example.class_var
        result = detector.call('modify_class')
        after = Example.class_var

        assert after == before + 1  # Class var did change
        assert result.has_changes  # But detector should see it
    ```

- Make method caching work for changes in class-level descriptors?

    ```python
    @pytest.mark.xfail(reason="Class-level descriptor modifications not tracked")
    def test_descriptor_modification_detected(self):
        """XFAIL: Modifying class descriptors should be detected."""
        class Validator:
            def __init__(self, max_val):
                self.max_val = max_val
            def __set_name__(self, owner, name):
                self.name = name
            def __get__(self, obj, objtype=None):
                return getattr(obj, f'_{self.name}', None)
            def __set__(self, obj, value):
                setattr(obj, f'_{self.name}', min(value, self.max_val))

        class Item:
            value = Validator(100)
            def __init__(self, val):
                self.value = val
            def change_max(self, new_max):
                type(self).value.max_val = new_max

        item = Item(50)
        detector = StateChangeDetector(item)
        result = detector.call('change_max', 200)

        assert Item.value.max_val == 200  # Descriptor did change
        assert result.has_changes
    ```

- Make method caching work for closures that modify outer scope variables? (is this possible? do we want to do this?

    ```python
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
        result = detector.call('increment')
        after = counter.get()

        assert after == before + 1  # State did change
        assert result.has_changes  # But detector should see it
    ```

- Make method caching work for methods that modify global state? (not actually sure if we want to do this)

    ```python
    @pytest.mark.xfail(reason="Global state changes are not tracked")
    def test_global_state_change_detected(self):
        """XFAIL: Global state changes should be detected."""
        global_state = {'counter': 0}

        class Example:
            def __init__(self):
                pass
            def modify_global(self):
                global_state['counter'] += 1

        obj = Example()
        detector = StateChangeDetector(obj)

        before = global_state['counter']
        result = detector.call('modify_global')
        after = global_state['counter']

        assert after == before + 1  # Global state did change
        assert result.has_changes  # But detector should see it
    ```

- Document limitations of method caching (e.g., doesn't track class/global state changes, IO writes, etc.)
- Make method caching more memory efficient (e.g., use more efficient diffs and avoid full copies)

    ```python
    @pytest.mark.xfail(reason="Deep copy of large objects is inefficient")
    def test_efficient_change_detection(self):
        """XFAIL: Change detection should be memory-efficient."""
        import tracemalloc

        class HugeObject:
            def __init__(self):
                self.data = bytearray(10 * 1024 * 1024)  # 10MB

            def tiny_change(self):
                self.data[0] = 42

        obj = HugeObject()
        detector = StateChangeDetector(obj)

        tracemalloc.start()
        result = detector.call('tiny_change')
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Should not use more than 2x the object size
        # (current impl uses 2x+ for before/after snapshots)
        assert peak < 25 * 1024 * 1024  # Less than 25MB
    ```

- Add a registry to patched objects
- Add ability to unpatch objects
- Add context manager to temporarily add or remove patches

### Bugs

- `StateChangeDetector` detects changes in some mutable objects even when there are none (false positives).

    ```python
    @pytest.mark.xfail(reason="False positives on iterator state")
    def test_iterator_state_false_positive(self):
        """XFAIL: Iterator internal state changes should not trigger change detection."""

        class Klass:
            def __init__(self):
                self.iter = iter(range(10))

            def noop(self):
                pass

        counter = Klass()
        detector = StateChangeDetector(counter)
        result = detector.call("noop")
        assert not result.has_changes
    ```

- FileExistsError when a method is patched multiple times. The solution is to create a registry for patched methods such that we don't double-patch methods.


## General Data Science

- Smart-bins from input data
  - Implement this <https://8080labs.com/blog/posts/find-best-bins-for-plotly-histogram/>
- Look into <https://bamboolib.8080labs.com/>

## pandas

- did you mean `.value_counts()` ?
- Styling preset
- The pandas SQLDatabase and SQLiteDatabase caching patches still try to connect to DB before accessing the cache this is probably happening during instantiation of the class. This makes the caching unusable when unconnected to the internet.
