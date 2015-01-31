import pytest
from pyrsistent import PVector, CheckedPVector, InvariantException


class Naturals(CheckedPVector):
    __type__ = int
    __invariant__ = lambda value: (value >= 0, 'Negative value')

def test_instantiate():
    x = Naturals([1, 2, 3])

    assert list(x) == [1, 2, 3]
    assert isinstance(x, Naturals)
    assert isinstance(x, PVector)

def test_append():
    x = Naturals()
    x2 = x.append(1)

    assert list(x2) == [1]
    assert isinstance(x2, Naturals)

def test_extend():
    x = Naturals()
    x2 = x.extend([1])

    assert list(x2) == [1]
    assert isinstance(x2, Naturals)

def test_set():
    x = Naturals([1, 2])
    x2 = x.set(1, 3)

    assert list(x2) == [1, 3]
    assert isinstance(x2, Naturals)


def test_invalid_type():
    with pytest.raises(TypeError):
        Naturals([1, 2.0])

    x = Naturals([1, 2])
    with pytest.raises(TypeError):
        x.append(3.0)

    with pytest.raises(TypeError):
        x.extend([3, 4.0])

    with pytest.raises(TypeError):
        x.set(1, 2.0)


def test_breaking_invariant():
    try:
        Naturals([1, -1])
        assert False
    except InvariantException as e:
        assert e.invariant_errors == ['Negative value']

    x = Naturals([1, 2])
    try:
        x.append(-1)
        assert False
    except InvariantException as e:
        assert e.invariant_errors == ['Negative value']

    try:
        x.extend([-1])
        assert False
    except InvariantException as e:
        assert e.invariant_errors == ['Negative value']

    try:
        x.set(1, -1)
        assert False
    except InvariantException as e:
        assert e.invariant_errors == ['Negative value']

# TODO
# Multiple allowed types
# Inheritance

def test_repr():
    x = Naturals([1, 2])

    assert str(x) == 'Naturals([1, 2])'