import pytest
from pyrsistent import CheckedPMap, InvariantException, PMap


class FloatToIntMap(CheckedPMap):
    __key_type__ = float
    __value_type__ = int
    __invariant__ = lambda key, value: (int(key) == value, 'Invalid mapping')

def test_instantiate():
    x = FloatToIntMap({1.1: 1, 2.3: 2})

    assert dict(x.items()) == {1.1: 1, 2.3: 2}
    assert isinstance(x, FloatToIntMap)
    assert isinstance(x, PMap)

def test_instantiate_empty():
    x = FloatToIntMap()

    assert dict(x.items()) == {}
    assert isinstance(x, FloatToIntMap)
    assert isinstance(x, PMap)

# def test_add():
#     x = Naturals()
#     x2 = x.add(1)
#
#     assert list(x2) == [1]
#     assert isinstance(x2, Naturals)
#
# def test_invalid_type():
#     with pytest.raises(TypeError):
#         Naturals([1, 2.0])
#
# def test_breaking_invariant():
#     try:
#         Naturals([1, -1])
#         assert False
#     except InvariantException as e:
#         assert e.invariant_errors == ['Negative value']
#
# def test_repr():
#     x = Naturals([1, 2])
#
#     assert str(x) == 'Naturals([1, 2])'
#
# def test_default_serialization():
#     x = Naturals([1, 2])
#
#     assert x.serialize() == set([1, 2])
#
# class StringNaturals(Naturals):
#     @staticmethod
#     def __serializer__(format, value):
#         return format.format(value)
#
# def test_custom_serialization():
#     x = StringNaturals([1, 2])
#
#     assert x.serialize("{0}") == set(["1", "2"])
#
# def test_create():
#     assert Naturals.create([1, 2]) == Naturals([1, 2])
#
# def test_evolver_returns_same_instance_when_no_updates():
#     x = Naturals([1, 2])
#     assert x.evolver().persistent() is x