import pytest
from hypothesis import given, strategies as st

from pyrsistent import (
    CheckedKeyTypeError, CheckedPMap, CheckedPSet, CheckedPVector,
    CheckedValueTypeError, InvariantException,
)


class NaturalMap(CheckedPMap):
    __key_type__ = int
    __value_type__ = int
    __invariant__ = lambda key, value: (value >= 0, 'negative value')


class NaturalSet(CheckedPSet):
    __type__ = int
    __invariant__ = lambda value: (value >= 0, 'negative value')


@pytest.mark.parametrize('operation', ['insert', 'replace', 'remove', 'clear'])
def test_checked_map_repeated_snapshot(operation):
    original = NaturalMap({1: 10, 2: 20})
    evolver = original.evolver()
    expected = dict(original)
    if operation == 'insert':
        evolver[3] = expected[3] = 30
    elif operation == 'replace':
        evolver[1] = expected[1] = 11
    elif operation == 'remove':
        evolver.remove(1)
        del expected[1]
    else:
        for key in original:
            evolver.remove(key)
        expected.clear()
    snapshot = evolver.persistent()
    assert dict(snapshot) == expected
    assert type(snapshot) is NaturalMap
    assert not evolver.is_dirty()
    assert evolver.persistent() is snapshot
    assert evolver.persistent() is snapshot
    assert len(evolver) == len(snapshot)
    assert original == {1: 10, 2: 20}


@pytest.mark.parametrize('operation', ['add', 'remove', 'clear'])
def test_checked_set_repeated_snapshot(operation):
    original = NaturalSet([1, 2])
    evolver = original.evolver()
    expected = set(original)
    if operation == 'add':
        evolver.add(3)
        expected.add(3)
    elif operation == 'remove':
        evolver.remove(1)
        expected.remove(1)
    else:
        for value in original:
            evolver.remove(value)
        expected.clear()
    snapshot = evolver.persistent()
    assert set(snapshot) == expected
    assert type(snapshot) is NaturalSet
    assert not evolver.is_dirty()
    assert evolver.persistent() is snapshot
    assert evolver.persistent() is snapshot
    assert len(evolver) == len(snapshot)
    assert original == {1, 2}


@given(st.lists(st.tuples(st.integers(0, 12), st.integers(0, 100)), min_size=1, max_size=40))
def test_checked_map_snapshot_trace(updates):
    original = NaturalMap()
    evolver = original.evolver()
    expected = {}
    snapshots = []
    for key, value in updates:
        evolver[key] = value
        expected[key] = value
        snapshot = evolver.persistent()
        assert dict(snapshot) == expected
        assert evolver.persistent() is snapshot
        evolver[key] = value  # A no-op must not return the pre-update map.
        assert evolver.persistent() is snapshot
        snapshots.append((snapshot, expected.copy()))
    assert not original
    for snapshot, contents in snapshots:
        assert dict(snapshot) == contents
        assert type(snapshot) is NaturalMap


@given(st.lists(st.tuples(st.booleans(), st.integers(0, 12)), min_size=1, max_size=40))
def test_checked_set_snapshot_trace(operations):
    original = NaturalSet()
    evolver = original.evolver()
    expected = set()
    snapshots = []
    for add, value in operations:
        if add:
            evolver.add(value)
            expected.add(value)
        elif value in expected:
            evolver.remove(value)
            expected.remove(value)
        snapshot = evolver.persistent()
        assert set(snapshot) == expected
        assert evolver.persistent() is snapshot
        snapshots.append((snapshot, expected.copy()))
    assert not original
    for snapshot, contents in snapshots:
        assert set(snapshot) == contents
        assert type(snapshot) is NaturalSet


@pytest.mark.parametrize('kind', ['map', 'set'])
def test_checked_snapshot_rejects_invalid_type_after_materializing(kind):
    original = NaturalMap({1: 1}) if kind == 'map' else NaturalSet([1])
    evolver = original.evolver()
    if kind == 'map':
        evolver[2] = 2
    else:
        evolver.add(2)
    snapshot = evolver.persistent()
    with pytest.raises(CheckedValueTypeError):
        if kind == 'map':
            evolver[3] = 'wrong'
        else:
            evolver.add('wrong')
    assert evolver.persistent() is snapshot


@pytest.mark.parametrize('kind', ['map', 'set'])
def test_checked_snapshot_invariant_still_checked_after_materializing(kind):
    original = NaturalMap({1: 1}) if kind == 'map' else NaturalSet([1])
    evolver = original.evolver()
    if kind == 'map':
        evolver[2] = 2
    else:
        evolver.add(2)
    snapshot = evolver.persistent()
    if kind == 'map':
        evolver[3] = -1
    else:
        evolver.add(-1)
    with pytest.raises(InvariantException):
        evolver.persistent()
    assert set(snapshot) == {1, 2}
    assert set(original) == {1}


def test_checked_map_key_type_still_checked_after_materializing():
    evolver = NaturalMap().evolver()
    evolver[1] = 1
    snapshot = evolver.persistent()
    with pytest.raises(CheckedKeyTypeError):
        evolver['wrong'] = 2
    assert evolver.persistent() is snapshot


def test_checked_vector_snapshot_control():
    class Naturals(CheckedPVector):
        __type__ = int
    original = Naturals([1])
    evolver = original.evolver()
    evolver.append(2)
    snapshot = evolver.persistent()
    assert evolver.persistent() is snapshot
    assert list(snapshot) == [1, 2]
    assert list(original) == [1]
