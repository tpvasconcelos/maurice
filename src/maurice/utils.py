import hashlib
from typing import Any

import dill


def hash_any(obj: Any) -> str:
    return hashlib.md5(dill.dumps(obj)).hexdigest()
