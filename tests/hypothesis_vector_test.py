"""
Hypothesis-based tests for pvector.
"""

import gc

from pytest import fixture

from pyrsistent import pvector

from hypothesis import given, strategies as st


class TestObject(object):
    """
    An object that might catch reference count errors sometimes.
    """
    def __init__(self):
        self.id = id(self)

    def __repr__(self):
        return "<%s>" % (self.id,)

    def __del__(self):
        # If self is a dangling memory reference this check might fail. Or
        # segfault :)
        if self.id != id(self):
            raise RuntimeError()


@fixture(scope="module")
def gc_when_done(request):
    request.addfinalizer(gc.collect)


def test_setup(gc_when_done):
    """
    Ensure we GC when tests finish.
    """


Lists = st.lists(st.builds(TestObject))
PVectors = Lists.map(lambda l: pvector(l))


@given(Lists)
def test_pvector(l):
    """
    ``pvector`` can be roundtripped to a list.
    """
    p = pvector(l)
    assert list(p) == l
    for i in range(len(l)):
        assert p[i] is l[i]


@given(PVectors)
def test_append(p):
    """
    ``append()`` adds an item to the end of the pvector.
    """
    obj = TestObject()
    result = p.append(obj)
    assert result[:-1] == p
    assert result[-1] is obj


@given(PVectors, PVectors)
def test_extend_with_pvector(p, p2):
    """
    ``extend()`` adds all items in given pvector to the end.
    """
    result = p.extend(p2)
    assert result[:len(p)] == p
    assert result[len(p):] == p2


@given(PVectors, st.lists(st.builds(TestObject)))
def test_extend_with_list(p, l):
    """
    ``extend()`` adds all items in given list to the end.
    """
    result = p.extend(l)
    assert result[:len(p)] == p
    assert list(result[len(p):]) == l
