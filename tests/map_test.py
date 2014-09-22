from collections import Mapping, Hashable
from operator import add
from pyrsistent import pmap, m
import pickle

def test_instance_of_hashable():
    assert isinstance(m(), Hashable)


def test_instance_of_map():
    assert isinstance(m(), Mapping)


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
    
    assert the_map is the_map.remove('b')
    
    empty_map = the_map.remove('a')
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

    map2 = map.remove('a')
    assert 'a' not in map2
    assert map2['b'] == 3


def test_initialization_with_many_elements():
    init_dict = dict([(str(x), x) for x in range(1700)])
    the_map = pmap(init_dict)

    assert len(the_map) == 1700
    assert the_map['16'] == 16
    assert the_map['1699'] == 1699
    assert the_map.set('256', 256) is the_map
 
    new_map = the_map.remove('1600')
    assert len(new_map) == 1699
    assert '1600' not in new_map
    assert new_map['1601'] == 1601
    
    # Some NOP properties
    assert new_map.remove('18888') is new_map
    assert '19999' not in new_map
    assert new_map['1500'] == 1500  
    assert new_map.set('1500', new_map['1500']) is new_map


def test_access_non_existing_element():
    map1 = pmap()
    assert len(map1) == 0
    
    map2 = map1.set('1', 1)
    assert '1' not in map1
    assert map2['1'] == 1
    assert '2' not in map2
    

def test_overwrite_existing_element():
    map1 = pmap({'a': 2})
    map2 = map1.set('a', 3)

    assert len(map2) == 1
    assert map2['a'] == 3

def test_supports_hash_and_equals():
    x = m(a=1, b=2, c=3)
    y = m(a=1, b=2, c=3)
    
    assert hash(x) == hash(y)
    assert x == y
    assert not (x != y)

def test_same_hash_when_content_the_same_but_underlying_vector_size_differs():
    x = pmap({x: x for x in range(1000)})
    y = pmap({10: 10, 200: 200, 700: 700})

    for z in x:
        if z not in y:
            x = x.remove(z)

    assert x == y
    assert hash(x) == hash(y)

def test_merge_with_multiple_arguments():
    # If same value is present in multiple sources, the rightmost is used.
    x = m(a=1, b=2, c=3)    
    y = x.merge(m(b=4, c=5), {'c': 6})

    assert y == m(a=1, b=4, c=6)

def test_merge_one_argument():
    x = m(a=1)

    assert x.merge(m(b=2)) == m(a=1, b=2)

def test_merge_no_arguments():
    x = m(a=1)

    assert x.merge() is x

def test_set_in_base_case():
    # Works as set when called with only one key
    x = m(a=1, b=2)
    
    assert x.set_in(['a'], 3) == m(a=3, b=2)

def test_set_in_base_case():
    # Works as set when called with only one key
    x = m(a=1, b=2)
    
    assert x.set_in(['a'], 3) == m(a=3, b=2)

def test_set_in_nested_maps():
    x = m(a=1, b=m(c=3, d=m(e=6, f=7)))
    
    assert x.set_in(['b', 'd', 'e'], 999) == m(a=1, b=m(c=3, d=m(e=999, f=7)))
    
def test_set_in_levels_missing():
    x = m(a=1, b=m(c=3))
    
    assert x.set_in(['b', 'd', 'e'], 999) == m(a=1, b=m(c=3, d=m(e=999)))


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

    map2 = map.set(dummy1, 11)
    assert map2[dummy1] == 11
    
    # Re-use existing structure when inserted element is the same
    assert map2.set(dummy1, 11) is map2
    
    map3 = map.set('a', 22)
    assert map3['a'] == 22
    assert map3[dummy3] == 3
    
    # Remove elements
    map4 = map.remove(dummy2)
    assert len(map4) == 2
    assert map4[dummy1] == 1
    assert dummy2 not in map4
    assert map4[dummy3] == 3
    
    assert map.remove(dummy4) == map
    
    # Empty map handling
    empty_map = map4.remove(dummy1).remove(dummy3)
    assert len(empty_map) == 0
    assert empty_map.remove(dummy1) == empty_map
    

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
    values = list(range(0, 2000))
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
    assert str(pmap({1: 2, 3: 4})) == "pmap({1: 2, 3: 4})"


def test_empty_truthiness():
    assert m(a=1)
    assert not m()

def test_merge_with():
    assert m(a=1).merge_with(add, m(a=2, b=4)) == m(a=3, b=4)
    assert m(a=1).merge_with(lambda l, r: l, m(a=2, b=4)) == m(a=1, b=4)

    def map_add(l, r):
        return dict(list(l.items()) + list(r.items()))

    assert m(a={'c': 3}).merge_with(map_add, m(a={'d': 4})) == m(a={'c': 3, 'd': 4})


def test_pickling_empty_map():
    assert pickle.loads(pickle.dumps(m(), -1)) == m()


def test_pickling_non_empty_vector():
    assert pickle.loads(pickle.dumps(m(a=1, b=2), -1)) == m(a=1, b=2)