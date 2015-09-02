"""
Hypothesis-based tests for pvector.
"""

import gc

from pyrsistent import pvector

from hypothesis import given, strategies as st


class TestObject(object):
    """
    An object that might catch reference count errors sometimes.
    """
    def __init__(self):
        self.id = id(self)

    def check(self):
        # If self is a dangling memory reference this check might fail. Or
        # segfault :)
        assert self.id == id(self)


def final_check(*pvectors):
    """
    Final sanity check on given pvectors.
    """
    gc.collect()
    for p in pvectors:
        for obj in p:
            obj.check()

PVectors = st.lists(st.builds(TestObject)).map(lambda l: pvector(l))


@given(PVectors)
def test_append(p):
    result = p.append(TestObject())
    assert result[:-1] == p
    final_check(result, p)
