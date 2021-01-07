from maurice import patch

patch()

import logging
from time import time

import numpy as np

breakpoint()
logging.basicConfig(level="DEBUG")


def main():
    from sklearn.svm import SVC

    X = np.array([[-1, -1], [-2, -1], [1, 1], [2, 1]])
    y = np.array([1, 1, 2, 2])

    svc = SVC()

    start = time()
    svc.fit(X=X, y=y)
    print(f"took {time() - start:.5f} seconds")

    print(svc.predict([[-0.8, -1]]))
    print(svc.predict([[-1, -0.8]]))


if __name__ == "__main__":
    main()
