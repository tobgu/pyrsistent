import six

from pyrsistent import pset, s
import pytest


def test_literalish_works():
    assert s() is pset()
    assert s(1, 2) == pset([1, 2])

def test_supports_hash():
    assert hash(s(1, 2)) == hash(s(1, 2))


def test_empty_truthiness():
    assert s(1)
    assert not s()

def test_contains_elements_that_it_was_initialized_with():
    initial = [1, 2, 3]
    s = pset(initial)

    assert set(s) == set(initial)
    assert len(s) == len(set(initial))


def test_is_immutable():
    s1 = pset([1])
    s2 = s1.add(2)

    assert s1 == pset([1])
    assert s2 == pset([1, 2])

    s3 = s2.remove(1)
    assert s2 == pset([1, 2])
    assert s3 == pset([2])

def test_remove_when_not_present():
    s1 = s(1, 2, 3)
    with pytest.raises(KeyError):
        s1.remove(4)

def test_discard():
    s1 = s(1, 2, 3)
    assert s1.discard(3) == s(1, 2)
    assert s1.discard(4) is s1


def test_is_iterable():
    assert sum(pset([1, 2, 3])) == 6


def test_contains():
    s = pset([1, 2, 3])

    assert 2 in s
    assert 4 not in s


def test_supports_set_operations():
    s1 = pset([1, 2, 3])
    s2 = pset([3, 4, 5])

    assert s1 | s2 == s(1, 2, 3, 4, 5)
    assert s1.union(s2) == s1 | s2

    assert s1 & s2 == s(3)
    assert s1.intersection(s2) == s1 & s2

    assert s1 - s2 == s(1, 2)
    assert s1.difference(s2) == s1 - s2

    assert s1 ^ s2 == s(1, 2, 4, 5)
    assert s1.symmetric_difference(s2) == s1 ^ s2


def test_supports_set_comparisons():
    s1 = s(1, 2, 3)
    s3 = s(1, 2)
    s4 = s(1, 2, 3)

    assert s(1, 2, 3, 3, 5) == s(1, 2, 3, 5)
    assert s1 != s3

    assert s3 < s1
    assert s3 <= s1
    assert s3 <= s4

    assert s1 > s3
    assert s1 >= s3
    assert s4 >= s3


def test_str():
    rep = str(pset([1, 2, 3]))
    assert rep == "pset([1, 2, 3])"

def test_is_disjoint():
    s1 = pset([1, 2, 3])
    s2 = pset([3, 4, 5])
    s3 = pset([4, 5])

    assert not s1.isdisjoint(s2)
    assert s1.isdisjoint(s3)

pytest.main()
