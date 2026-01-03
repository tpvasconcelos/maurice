from __future__ import annotations

from time import time

from sklearn.datasets import make_circles
from sklearn.svm import SVC

import maurice
from maurice.utils import _setup_debug_logging

maurice.patch()
_setup_debug_logging()


def main() -> None:
    X, y = make_circles(n_samples=100_000, factor=0.5, noise=0.1, random_state=42)

    svc = SVC(gamma="scale")

    start = time()
    svc.fit(X=X, y=y)
    print(f"fit: took {time() - start:.5f} seconds")
    # Raw unpatched:        1.73s
    # Patched (cold-start): 1.74s
    # Patched (cache hit):  0.003s

    start = time()
    print(svc.predict([[-0.8, -1]]))
    print(svc.predict([[-1, -0.8]]))
    print(f"predict: took {time() - start:.5f} seconds")


if __name__ == "__main__":
    main()
