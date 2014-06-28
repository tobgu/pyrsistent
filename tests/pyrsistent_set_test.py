from pyrsistent import pset, s
import pytest


def test_literalish_works():
    assert s() is pset()
    assert s(1, 2) == pset([1, 2])

def test_supports_hash():
    assert hash(s(1, 2)) == hash(s(1, 2))


def test_contains_elements_that_it_was_initialized_with():
    initial = [1, 2, 3]
    s = pset(initial)

    assert set(s) == set(initial)
    assert len(s) == len(set(initial))


def test_is_immutable():
    s1 = pset([1])
    s2 = s1.assoc(2)

    assert s1 == pset([1])
    assert s2 == pset([1, 2])

    s3 = s2.dissoc(1)
    assert s2 == pset([1, 2])
    assert s3 == pset([2])


def test_is_iterable():
    assert sum(pset([1, 2, 3])) == 6


def test_contains():
    s = pset([1, 2, 3])

    assert 2 in s
    assert 4 not in s


def test_behaves_set_like():
    # This functionality should come "for free"

    s1 = pset([1, 2, 3])
    s2 = pset([3, 4, 5])

    assert sorted(pset([1, 2, 3, 3, 5])) == [1, 2, 3, 5]

    assert sorted(s1 | s2) == [1, 2, 3, 4, 5]
    assert sorted(s1 & s2) == [3]


def test_str():
    assert str(pset([1, 2, 3])) == "pset([1, 2, 3])"

def test_is_disjoint():
    s1 = pset([1, 2, 3])
    s2 = pset([3, 4, 5])
    s3 = pset([4, 5])

    assert not s1.isdisjoint(s2)
    assert s1.isdisjoint(s3)



pytest.main()
