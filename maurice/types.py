from typing import Any, Callable, NewType, Protocol, Type, TypeVar, cast

# ===================================================
# StatefulClass(Protocol)
# ===================================================


class StatefulClass(Protocol):
    def __getstate__(self) -> dict:
        ...

    def __setstate__(self, state: dict) -> None:
        ...


# ===================================================
# BoundMethodType(Protocol)
# ===================================================


BoundMethodInstanceType = NewType("BoundMethodInstanceType", object)
BoundMethodClassType = Type[BoundMethodInstanceType]
BoundMethodReturnType = TypeVar("BoundMethodReturnType")


class BoundMethodType(Protocol):
    __name__: str
    __self__: BoundMethodInstanceType

    def __call__(self, *args: Any, **kwargs: Any) -> BoundMethodReturnType:
        ...


def type_bound_method(bound_method: Callable[..., BoundMethodReturnType]) -> BoundMethodType:
    return cast(BoundMethodType, bound_method)


# ===================================================
# --- END ---
# ===================================================

if __name__ == "__main__":

    def return_instance_of_bound_method(method: BoundMethodType) -> BoundMethodInstanceType:
        return method.__self__

    def return_class_of_bound_method(method: BoundMethodType) -> BoundMethodClassType:
        return method.__self__.__class__

    def run_bounded_method(method: BoundMethodType, *args: Any, **kwargs: Any) -> BoundMethodReturnType:
        return method(*args, **kwargs)

    class MyClass:
        def __init__(self) -> None:
            pass

        def my_method(self) -> bool:
            return True

    # doesnt work out of the box...
    my_bound_method = MyClass().my_method
    print(return_instance_of_bound_method(my_bound_method))
    print(return_class_of_bound_method(my_bound_method))
    print(run_bounded_method(my_bound_method))

    # you need to use typing.cast() for it to work...
    my_bound_method = type_bound_method(MyClass().my_method)
    print(return_instance_of_bound_method(my_bound_method))
    print(return_class_of_bound_method(my_bound_method))
    print(run_bounded_method(my_bound_method))

    # let's try one more example
    from pathlib import Path
    my_bound_method = type_bound_method(Path().joinpath)
    print(return_instance_of_bound_method(my_bound_method))
    print(return_class_of_bound_method(my_bound_method))
    print(run_bounded_method(my_bound_method, "some_arg", "and_another"))
