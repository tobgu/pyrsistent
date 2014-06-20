from pyrsistent import pmap, m
import pytest


def test_literalish_works():
    assert m() is pmap()
    assert m(a=1, b=2) == pmap({'a': 1, 'b': 2})

def test_empty_initialization():
    map = pmap()
    assert len(map) == 0


def test_initialization_with_one_element():
    the_map = pmap({'a': 2})
    assert len(the_map) == 1
    assert the_map['a'] == 2
    assert the_map.a == 2
    assert 'a' in the_map
    
    assert the_map is the_map.without('b')
    
    empty_map = the_map.without('a')
    assert len(empty_map) == 0
    assert 'a' not in empty_map


def test_various_iterations():
    assert set(['a', 'b']) == set(m(a=1, b=2))
    assert ['a', 'b'] == sorted(m(a=1, b=2).keys())

    assert set([1, 2]) == set(m(a=1, b=2).itervalues())
    assert [1, 2] == sorted(m(a=1, b=2).values())

    assert set([('a', 1), ('b', 2)]) == set(m(a=1, b=2).iteritems())
    assert set([('a', 1), ('b', 2)]) == set(m(a=1, b=2).items())


def test_initialization_with_two_elements():
    map = pmap({'a': 2, 'b': 3})
    assert len(map) == 2
    assert map['a'] == 2
    assert map['b'] == 3

    map2 = map.without('a')
    assert 'a' not in map2
    assert map2['b'] == 3


def test_initialization_with_many_elements():
    init_dict = dict([(str(x), x) for x in range(1700)])
    the_map = pmap(init_dict)

    assert len(the_map) == 1700
    assert the_map['16'] == 16
    assert the_map['1699'] == 1699
    assert the_map.assoc('256', 256) is the_map
 
    new_map = the_map.without('1600')
    assert len(new_map) == 1699
    assert '1600' not in new_map
    assert new_map['1601'] == 1601
    
    # Some NOP properties
    assert new_map.without('18888') is new_map
    assert '19999' not in new_map
    assert new_map['1500'] == 1500  
    assert new_map.assoc('1500', new_map['1500']) is new_map


def test_access_non_existing_element():
    map1 = pmap()
    assert len(map1) == 0
    
    map2 = map1.assoc('1', 1)
    assert '1' not in map1
    assert map2['1'] == 1
    assert '2' not in map2
    

def test_overwrite_existing_element():
    map1 = pmap({'a': 2})
    map2 = map1.assoc('a', 3)

    assert len(map2) == 1
    assert map2['a'] == 3


class HashDummy(object):
    def __hash__(self):
        return 6528039219058920  # Hash of '33'

    def __eq__(self, other):
        return self is other


def test_hash_collision_is_correctly_resolved():

    dummy1 = HashDummy()
    dummy2 = HashDummy()
    dummy3 = HashDummy()
    dummy4 = HashDummy()

    map = pmap({dummy1: 1, dummy2: 2, dummy3: 3})
    assert map[dummy1] == 1
    assert map[dummy2] == 2
    assert map[dummy3] == 3
    assert dummy4 not in map
    
    keys = set()
    values = set()
    for k, v in map.iteritems():
        keys.add(k)
        values.add(v)

    assert keys == set([dummy1, dummy2, dummy3])
    assert values == set([1, 2, 3])

    map2 = map.assoc(dummy1, 11)
    assert map2[dummy1] == 11
    
    # Re-use existing structure when inserted element is the same
    assert map2.assoc(dummy1, 11) is map2
    
    map3 = map.assoc('a', 22)
    assert map3['a'] == 22
    assert map3[dummy3] == 3
    
    # Remove elements
    map4 = map.without(dummy2)
    assert len(map4) == 2
    assert map4[dummy1] == 1
    assert dummy2 not in map4
    assert map4[dummy3] == 3
    
    assert map.without(dummy4) == map
    
    # Empty map handling
    empty_map = map4.without(dummy1).without(dummy3)
    assert len(empty_map) == 0
    assert empty_map.without(dummy1) == empty_map
    

def test_bitmap_indexed_iteration():
    map = pmap({'a': 2, 'b': 1})
    keys = set()
    values = set()
    
    count = 0
    for k, v in map.iteritems():
        count += 1
        keys.add(k)
        values.add(v)
    
    assert count == 2
    assert keys == {'a', 'b'}
    assert values == {2, 1}


def test_iteration_with_many_elements():
    values = range(0, 2000)
    keys = [str(x) for x in values]
    init_dict = dict(zip(keys, values))
    
    hash_dummy1 = HashDummy()
    hash_dummy2 = HashDummy()
    
    # Throw in a couple of hash collision nodes to tests
    # those properly as well
    init_dict[hash_dummy1] = 12345
    init_dict[hash_dummy2] = 54321
    map = pmap(init_dict)

    actual_values = set()
    actual_keys = set()
    
    for k, v in map.iteritems():
        actual_values.add(v)
        actual_keys.add(k)
        
    assert actual_keys == set(keys + [hash_dummy1, hash_dummy2])
    assert actual_values == set(values + [12345, 54321])


def test_str():
    assert str(pmap({1: 2, 3: 4})) == "{1: 2, 3: 4}"

pytest.main()
