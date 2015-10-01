import pytest

from pyrsistent import pmap
import random

import gc


def test_segfault_issue_52():
    threshold = gc.get_threshold()
    gc.set_threshold(1, 1, 1)  # fail fast

    v = [pmap()]

    def step():
        depth = random.randint(1, 10)
        path = random.sample(range(100000), depth)
        v[0] = v[0].transform(path, "foo")

    for i in range(1000):  # usually crashes after 10-20 steps
        while True:
            try:
                step()
                break
            except AttributeError:  # evolver on string
                continue

    gc.set_threshold(*threshold)
