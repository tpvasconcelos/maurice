from pathlib import Path

import pytest

from maurice.utils import hash_any


@pytest.mark.parametrize(
    "obj,expected_hash",
    (
        # simple types like int and str
        (42, "0837e03ec8dab5a359b25740047e415f"),
        ("Hello, World!", "4b25fee49251a68a90b925dc611a4f8d"),
        # a more complex and nexted object
        (
            [
                (1, 2, 3),
                open(Path(__file__)),
                {"a": 1, 1: "a", "nested": {"I": "am", "nested": "indeed"}},
            ],
            "d10c2f17ee467ac4d90d44c9f031b04d",
        ),
    ),
)
def test_hash_any(obj, expected_hash: str) -> None:
    hash_str = hash_any(obj=obj)
    assert isinstance(hash_str, str)
    assert hash_str == expected_hash
