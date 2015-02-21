import pytest
from pyrsistent import CheckedPMap, InvariantException, PMap, CheckedType


class FloatToIntMap(CheckedPMap):
    __key_type__ = float
    __value_type__ = int
    __invariant__ = lambda key, value: (int(key) == value, 'Invalid mapping')

def test_instantiate():
    x = FloatToIntMap({1.1: 1, 2.3: 2})

    assert dict(x.items()) == {1.1: 1, 2.3: 2}
    assert isinstance(x, FloatToIntMap)
    assert isinstance(x, PMap)
    assert isinstance(x, CheckedType)

def test_instantiate_empty():
    x = FloatToIntMap()

    assert dict(x.items()) == {}
    assert isinstance(x, FloatToIntMap)

def test_set():
     x = FloatToIntMap()
     x2 = x.set(1.0, 1)

     assert x2[1.0] == 1
     assert isinstance(x2, FloatToIntMap)

def test_invalid_key_type():
     with pytest.raises(TypeError):
         FloatToIntMap({1: 1})

def test_invalid_value_type():
     with pytest.raises(TypeError):
         FloatToIntMap({1.0: 1.0})

def test_breaking_invariant():
     try:
         FloatToIntMap({1.3: 2})
         assert False
     except InvariantException as e:
        assert e.invariant_errors == ['Invalid mapping']

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