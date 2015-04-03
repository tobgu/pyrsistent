# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from collections import (Sequence, Mapping, Set, Hashable, Container, Iterable, Sized)
from functools import wraps, reduce
from itertools import chain, islice
from numbers import Integral
import sys
import re

import six

from _pyrsistent_version import __version__

def _bitcount(val):
    return bin(val).count("1")

BRANCH_FACTOR = 32
BIT_MASK = BRANCH_FACTOR - 1
SHIFT = _bitcount(BIT_MASK)

def _comparator(f):
    @wraps(f)
    def wrapper(*args, **kwds):
        if isinstance(args[0], PVector) and isinstance(args[1], PVector):
            return f(*args, **kwds)
        return NotImplemented
    return wrapper


class _PVectorImpl(object):
    """
    Support structure for PVector that implements structural sharing for vectors using a trie.
    """
    __slots__ = ('_count', '_shift', '_root', '_tail', '_tail_offset')

    def __new__(cls, count, shift, root, tail):
        self = super(_PVectorImpl, cls).__new__(cls)
        self._count = count
        self._shift = shift
        self._root = root
        self._tail = tail

        # Derived attribute stored for performance
        self._tail_offset = self._count - len(self._tail)
        return self

    def __len__(self):
        return self._count

    def __getitem__(self, index):
        if isinstance(index, slice):
            # There are more conditions than the below where it would be OK to
            # return ourselves, implement those...
            if index.start is None and index.stop is None and index.step is None:
                return self

            # This is a bit nasty realizing the whole structure as a list before
            # slicing it but it is the fastest way I've found to date, and it's easy :-)
            return _EMPTY_PVECTOR.extend(self.tolist()[index])

        if index < 0:
            index += self._count

        return _PVectorImpl._node_for(self, index)[index & BIT_MASK]

    def __add__(self, other):
        return self.extend(other)

    def __repr__(self):
        return 'pvector({0})'.format(str(self.tolist()))

    def __str__(self):
        return self.__repr__()

    def __iter__(self):
        # This is kind of lazy and will produce some memory overhead but it is the fasted method
        # by far of those tried since it uses the speed of the built in python list directly.
        return iter(self.tolist())

    @_comparator
    def __ne__(self, other):
        return self.tolist() != other.tolist()

    @_comparator
    def __eq__(self, other):
        return self is other or self.tolist() == other.tolist()

    @_comparator
    def __gt__(self, other):
        return self.tolist() > other.tolist()

    @_comparator
    def __lt__(self, other):
        return self.tolist() < other.tolist()

    @_comparator
    def __ge__(self, other):
        return self.tolist() >= other.tolist()

    @_comparator
    def __le__(self, other):
        return self.tolist() <= other.tolist()

    def __mul__(self, times):
        if times <= 0 or self is _EMPTY_PVECTOR:
            return _EMPTY_PVECTOR

        if times == 1:
            return self

        return _EMPTY_PVECTOR.extend(times * self.tolist())

    __rmul__ = __mul__

    def _fill_list(self, node, shift, the_list):
        if shift:
            shift -= SHIFT
            for n in node:
                self._fill_list(n, shift, the_list)
        else:
            the_list.extend(node)

    def tolist(self):
        """
        The fastest way to convert the vector into a python list.
        """
        the_list = []
        self._fill_list(self._root, self._shift, the_list)
        the_list.extend(self._tail)
        return the_list

    def _totuple(self):
        """
        Returns the content as a python tuple.
        """
        return tuple(self.tolist())

    def __hash__(self):
        # Taking the easy way out again...
        return hash(self._totuple())

    def set_in(self, keys, val):
        import warnings
        warnings.warn("set_in is deprecated, use transform instead", DeprecationWarning, stacklevel=2)
        return self.transform(keys, val)

    def transform(self, *transformations):
        return _transform(self, transformations)

    def __reduce__(self):
        # Pickling support
        return pvector, (self.tolist(),)

    def mset(self, *args):
        if len(args) % 2:
            raise TypeError("mset expected an even number of arguments")

        evolver = self.evolver()
        for i in range(0, len(args), 2):
            evolver[args[i]] = args[i+1]

        return evolver.persistent()

    class Evolver(object):
        __slots__ = ('_count', '_shift', '_root', '_tail', '_tail_offset', '_dirty_nodes',
                     '_extra_tail', '_cached_leafs', '_orig_pvector')

        def __init__(self, v):
            self._reset(v)

        def __getitem__(self, index):
            if not isinstance(index, Integral):
                raise TypeError("'%s' object cannot be interpreted as an index" % type(index).__name__)

            if index < 0:
                index += self._count + len(self._extra_tail)

            if self._count <= index < self._count + len(self._extra_tail):
                return self._extra_tail[index - self._count]

            return _PVectorImpl._node_for(self, index)[index & BIT_MASK]

        def _reset(self, v):
            self._count = v._count
            self._shift = v._shift
            self._root = v._root
            self._tail = v._tail
            self._tail_offset = v._tail_offset
            self._dirty_nodes = {}
            self._cached_leafs = {}
            self._extra_tail = []
            self._orig_pvector = v

        def append(self, element):
            self._extra_tail.append(element)
            return self

        def extend(self, iterable):
            self._extra_tail.extend(iterable)
            return self

        def set(self, index, val):
            self[index] = val
            return self

        def __setitem__(self, index, val):
            if not isinstance(index, Integral):
                raise TypeError("'%s' object cannot be interpreted as an index" % type(index).__name__)

            if index < 0:
                index += self._count + len(self._extra_tail)

            if 0 <= index < self._count:
                node = self._cached_leafs.get(index >> SHIFT)
                if node:
                    node[index & BIT_MASK] = val
                elif index >= self._tail_offset:
                    if id(self._tail) not in self._dirty_nodes:
                        self._tail = list(self._tail)
                        self._dirty_nodes[id(self._tail)] = True
                        self._cached_leafs[index >> SHIFT] = self._tail
                    self._tail[index & BIT_MASK] = val
                else:
                    self._root = self._do_set(self._shift, self._root, index, val)
            elif self._count <= index < self._count + len(self._extra_tail):
                self._extra_tail[index - self._count] = val
            elif index == self._count + len(self._extra_tail):
                self._extra_tail.append(val)
            else:
                raise IndexError("Index out of range: %s" % (index,))

        def _do_set(self, level, node, i, val):
            if id(node) in self._dirty_nodes:
                ret = node
            else:
                ret = list(node)
                self._dirty_nodes[id(ret)] = True

            if level == 0:
                ret[i & BIT_MASK] = val
                self._cached_leafs[i >> SHIFT] = ret
            else:
                sub_index = (i >> level) & BIT_MASK  # >>>
                ret[sub_index] = self._do_set(level - SHIFT, node[sub_index], i, val)

            return ret

        def persistent(self):
            result = self._orig_pvector
            if self.is_dirty():
                result = _PVectorImpl(self._count, self._shift, self._root, self._tail).extend(self._extra_tail)
                self._reset(result)

            return result

        def __len__(self):
            return self._count + len(self._extra_tail)

        def is_dirty(self):
            return bool(self._dirty_nodes or self._extra_tail)

    def evolver(self):
        return _PVectorImpl.Evolver(self)

    def set(self, i, val):
        # This method could be implemented by a call to mset() but doing so would cause
        # a ~5 X performance penalty on PyPy (considered the primary platform for this implementation
        #  of PVector) so we're keeping this implementation for now.

        if not isinstance(i, Integral):
            raise TypeError("'%s' object cannot be interpreted as an index" % type(i).__name__)

        if i < 0:
            i += self._count

        if 0 <= i < self._count:
            if i >= self._tail_offset:
                new_tail = list(self._tail)
                new_tail[i & BIT_MASK] = val
                return _PVectorImpl(self._count, self._shift, self._root, new_tail)

            return _PVectorImpl(self._count, self._shift, self._do_set(self._shift, self._root, i, val), self._tail)

        if i == self._count:
            return self.append(val)

        raise IndexError("Index out of range: %s" % (i,))

    def _do_set(self, level, node, i, val):
        ret = list(node)
        if level == 0:
            ret[i & BIT_MASK] = val
        else:
            sub_index = (i >> level) & BIT_MASK  # >>>
            ret[sub_index] = self._do_set(level - SHIFT, node[sub_index], i, val)

        return ret

    @staticmethod
    def _node_for(pvector_like, i):
        if 0 <= i < pvector_like._count:
            if i >= pvector_like._tail_offset:
                return pvector_like._tail

            node = pvector_like._root
            for level in range(pvector_like._shift, 0, -SHIFT):
                node = node[(i >> level) & BIT_MASK]  # >>>

            return node

        raise IndexError("Index out of range: %s" % (i,))

    def _create_new_root(self):
        new_shift = self._shift

        # Overflow root?
        if (self._count >> SHIFT) > (1 << self._shift): # >>>
            new_root = [self._root, self._new_path(self._shift, self._tail)]
            new_shift += SHIFT
        else:
            new_root = self._push_tail(self._shift, self._root, self._tail)

        return new_root, new_shift

    def append(self, val):
        if len(self._tail) < BRANCH_FACTOR:
            new_tail = list(self._tail)
            new_tail.append(val)
            return _PVectorImpl(self._count + 1, self._shift, self._root, new_tail)

        # Full tail, push into tree
        new_root, new_shift = self._create_new_root()
        return _PVectorImpl(self._count + 1, new_shift, new_root, [val])

    def _new_path(self, level, node):
        if level == 0:
            return node

        return [self._new_path(level - SHIFT, node)]

    def _mutating_insert_tail(self):
        self._root, self._shift = self._create_new_root()
        self._tail = []

    def _mutating_fill_tail(self, offset, sequence):
        max_delta_len = BRANCH_FACTOR - len(self._tail)
        delta = sequence[offset:offset + max_delta_len]
        self._tail.extend(delta)
        delta_len = len(delta)
        self._count += delta_len
        return offset + delta_len

    def _mutating_extend(self, sequence):
        offset = 0
        sequence_len = len(sequence)
        while offset < sequence_len:
            offset = self._mutating_fill_tail(offset, sequence)
            if len(self._tail) == BRANCH_FACTOR:
                self._mutating_insert_tail()

        self._tail_offset = self._count - len(self._tail)

    def extend(self, obj):
        # Mutates the new vector directly for efficiency but that's only an
        # implementation detail, once it is returned it should be considered immutable
        l = obj.tolist() if isinstance(obj, _PVectorImpl) else list(obj)
        if l:
            new_vector = self.append(l[0])
            new_vector._mutating_extend(l[1:])
            return new_vector

        return self

    def _push_tail(self, level, parent, tail_node):
        """
        if parent is leaf, insert node,
        else does it map to an existing child? ->
             node_to_insert = push node one more level
        else alloc new path

        return  node_to_insert placed in copy of parent
        """
        ret = list(parent)

        if level == SHIFT:
            ret.append(tail_node)
            return ret

        sub_index = ((self._count - 1) >> level) & BIT_MASK  # >>>
        if len(parent) > sub_index:
            ret[sub_index] = self._push_tail(level - SHIFT, parent[sub_index], tail_node)
            return ret

        ret.append(self._new_path(level - SHIFT, tail_node))
        return ret

    def index(self, value, *args, **kwargs):
        return self.tolist().index(value, *args, **kwargs)

    def count(self, value):
        return self.tolist().count(value)

@six.add_metaclass(ABCMeta)
class PVector(object):
    """
    Persistent vector implementation. Meant as a replacement for the cases where you would normally
    use a Python list.

    Do not instantiate directly, instead use the factory functions :py:func:`v` and :py:func:`pvector` to
    create an instance.

    Heavily influenced by the persistent vector available in Clojure. Initially this was more or
    less just a port of the Java code for the Clojure vector. It has since been modified and to
    some extent optimized for usage in Python.

    The vector is organized as a trie, any mutating method will return a new vector that contains the changes. No
    updates are done to the original vector. Structural sharing between vectors are applied where possible to save
    space and to avoid making complete copies.

    This structure corresponds most closely to the built in list type and is intended as a replacement. Where the
    semantics are the same (more or less) the same function names have been used but for some cases it is not possible,
    for example assignments.

    The PVector implements the Sequence protocol and is Hashable.

    Inserts are amortized O(1). Random access is log32(n) where n is the size of the vector.

    The following are examples of some common operations on persistent vectors:

    >>> p = v(1, 2, 3)
    >>> p2 = p.append(4)
    >>> p3 = p2.extend([5, 6, 7])
    >>> p
    pvector([1, 2, 3])
    >>> p2
    pvector([1, 2, 3, 4])
    >>> p3
    pvector([1, 2, 3, 4, 5, 6, 7])
    >>> p3[5]
    6
    >>> p.set(1, 99)
    pvector([1, 99, 3])
    >>>
    """

    @abstractmethod
    def __len__(self):
        """
        >>> len(v(1, 2, 3))
        3
        """

    @abstractmethod
    def __getitem__(self, index):
        """
        Get value at index. Full slicing support.

        >>> v1 = v(5, 6, 7, 8)
        >>> v1[2]
        7
        >>> v1[1:3]
        pvector([6, 7])
        """

    @abstractmethod
    def __add__(self, other):
        """
        >>> v1 = v(1, 2)
        >>> v2 = v(3, 4)
        >>> v1 + v2
        pvector([1, 2, 3, 4])
        """

    @abstractmethod
    def __mul__(self, times):
        """
        >>> v1 = v(1, 2)
        >>> 3 * v1
        pvector([1, 2, 1, 2, 1, 2])
        """

    @abstractmethod
    def __hash__(self):
        """
        >>> v1 = v(1, 2, 3)
        >>> v2 = v(1, 2, 3)
        >>> hash(v1) == hash(v2)
        True
        """

    @abstractmethod
    def evolver(self):
        """
        Create a new evolver for this pvector. The evolver acts as a mutable view of the vector
        with "transaction like" semantics. No part of the underlying vector i updated, it is still
        fully immutable. Furthermore multiple evolvers created from the same pvector do not
        interfere with each other.

        You may want to use an evolver instead of working directly with the pvector in the
        following cases:

        * Multiple updates are done to the same vector and the intermediate results are of no
          interest. In this case using an evolver may be a more efficient and easier to work with.
        * You need to pass a vector into a legacy function or a function that you have no control
          over which performs in place mutations of lists. In this case pass an evolver instance
          instead and then create a new pvector from the evolver once the function returns.

        The following example illustrates a typical workflow when working with evolvers. It also
        displays most of the API (which i kept small by design, you should not be tempted to
        use evolvers in excess ;-)).

        Create the evolver and perform various mutating updates to it:
        >>> v1 = v(1, 2, 3, 4, 5)
        >>> e = v1.evolver()
        >>> e[1] = 22
        >>> _ = e.append(6)
        >>> _ = e.extend([7, 8, 9])
        >>> e[8] += 1
        >>> len(e)
        9

        The underlying pvector remains the same:
        >>> v1
        pvector([1, 2, 3, 4, 5])

        The changes are kept in the evolver. An updated pvector can be created using the
        pvector() function on the evolver.
        >>> v2 = e.persistent()
        >>> v2
        pvector([1, 22, 3, 4, 5, 6, 7, 8, 10])

        The new pvector will share data with the original pvector in the same way that would have
        been done if only using operations on the pvector.
        """

    @abstractmethod
    def mset(self, *args):
        """
        Return a new vector with elements in specified positions replaced by values (multi set).

        Elements on even positions in the argument list are interpreted as indexes while
        elements on odd positions are considered values.

        >>> v1 = v(1, 2, 3)
        >>> v1.mset(0, 11, 2, 33)
        pvector([11, 2, 33])
        """

    @abstractmethod
    def set(self, i, val):
        """
        Return a new vector with element at position i replaced with val. The original vector remains unchanged.

        Setting a value one step beyond the end of the vector is equal to appending. Setting beyond that will
        result in an IndexError.

        >>> v1 = v(1, 2, 3)
        >>> v1.set(1, 4)
        pvector([1, 4, 3])
        >>> v1.set(3, 4)
        pvector([1, 2, 3, 4])
        >>> v1.set(-1, 4)
        pvector([1, 2, 4])
        """

    @abstractmethod
    def append(self, val):
        """
        Return a new vector with val appended.

        >>> v1 = v(1, 2)
        >>> v1.append(3)
        pvector([1, 2, 3])
        """

    @abstractmethod
    def extend(self, obj):
        """
        Return a new vector with all values in obj appended to it. Obj may be another
        PVector or any other Iterable.

        >>> v1 = v(1, 2, 3)
        >>> v1.extend([4, 5])
        pvector([1, 2, 3, 4, 5])
        """

    @abstractmethod
    def set_in(self, keys, val):
        """
        Insert val into nested persistent structure at position specified by Iterable keys. Any levels that
        do not exist will be inserted as new PMaps.

        >>> v1 = v(1, 2, m(a=5, b=6))
        >>> v1.set_in((2, 'b'), 17)
        pvector([1, 2, pmap({'a': 5, 'b': 17})])
        >>> v1.set_in((2, 'c', 'd'), 17)
        pvector([1, 2, pmap({'a': 5, 'c': pmap({'d': 17}), 'b': 6})])
        """

    @abstractmethod
    def index(self, value, *args, **kwargs):
        """
        Return first index of value. Additional indexes may be supplied to limit the search to a
        sub range of the vector.

        >>> v1 = v(1, 2, 3, 4, 3)
        >>> v1.index(3)
        2
        >>> v1.index(3, 3, 5)
        4
        """

    @abstractmethod
    def count(self, value):
        """
        Return the number of times that value appears in the vector.

        >>> v1 = v(1, 4, 3, 4)
        >>> v1.count(4)
        2
        """

    @abstractmethod
    def transform(self, *transformations):
        """
        Transform arbitrarily complex combinations of PVectors and PMaps. A transformation
        consists of two parts. One match expression that specifies which elements to transform
        and one transformation function that performs the actual transformation.

        >>> news_paper = freeze({'articles': [{'author': 'Sara', 'content': 'A short article'},
        ...                                   {'author': 'Steve', 'content': 'A slightly longer article'}],
        ...                      'weather': {'temperature': '11C', 'wind': '5m/s'}})
        >>> short_news = news_paper.transform(['articles', ny, 'content'], lambda c: c[:25] + '...' if len(c) > 25 else c)
        >>> very_short_news = news_paper.transform(['articles', ny, 'content'], lambda c: c[:15] + '...' if len(c) > 15 else c)
        >>> very_short_news.articles[0].content
        'A short article'
        >>> very_short_news.articles[1].content
        'A slightly long...'

        When nothing has been transformed the original data structure is kept

        >>> short_news is news_paper
        True
        >>> very_short_news is news_paper
        False
        >>> very_short_news.articles[0] is news_paper.articles[0]
        True
        """

_EMPTY_PVECTOR = _PVectorImpl(0, SHIFT, [], [])
PVector.register(_PVectorImpl)
Sequence.register(PVector)
Hashable.register(PVector)

def _pvector(iterable=()):
    """
    Create a new persistent vector containing the elements in iterable.

    >>> v1 = pvector([1, 2, 3])
    >>> v1
    pvector([1, 2, 3])
    """
    return _EMPTY_PVECTOR.extend(iterable)

try:
    # Use the C extension as underlying trie implementation if it is available
    from pvectorc import pvector
    PVector.register(type(pvector()))
except ImportError:
    pvector = _pvector


def v(*elements):
    """
    Create a new persistent vector containing all parameters to this function.

    >>> v1 = v(1, 2, 3)
    >>> v1
    pvector([1, 2, 3])
    """
    return pvector(elements)


####################### PMap #####################################
class PMap(object):
    """
    Persistent map/dict. Tries to follow the same naming conventions as the built in dict where feasible.

    Do not instantiate directly, instead use the factory functions :py:func:`m` or :py:func:`pmap` to
    create an instance.

    Was originally written as a very close copy of the Clojure equivalent but was later rewritten to closer
    re-assemble the python dict. This means that a sparse vector (a PVector) of buckets is used. The keys are
    hashed and the elements inserted at position hash % len(bucket_vector). Whenever the map size exceeds 2/3 of
    the containing vectors size the map is reallocated to a vector of double the size. This is done to avoid
    excessive hash collisions.

    This structure corresponds most closely to the built in dict type and is intended as a replacement. Where the
    semantics are the same (more or less) the same function names have been used but for some cases it is not possible,
    for example assignments and deletion of values.

    PMap implements the Mapping protocol and is Hashable.

    Random access and insert is log32(n) where n is the size of the map.

    The following are examples of some common operations on persistent maps

    >>> m1 = m(a=1, b=3)
    >>> m2 = m1.set('c', 3)
    >>> m3 = m2.remove('a')
    >>> m1
    pmap({'a': 1, 'b': 3})
    >>> m2
    pmap({'a': 1, 'c': 3, 'b': 3})
    >>> m3
    pmap({'c': 3, 'b': 3})
    >>> m3['c']
    3
    """
    __slots__ = ('_size', '_buckets')

    def __new__(cls, size, buckets):
        self = super(PMap, cls).__new__(cls)
        self._size = size
        self._buckets = buckets
        return self

    @staticmethod
    def _get_bucket(buckets, key):
        index = hash(key) % len(buckets)
        bucket = buckets[index]
        return index, bucket

    @staticmethod
    def _getitem(buckets, key):
        _, bucket = PMap._get_bucket(buckets, key)
        if bucket:
            for k, v in bucket:
                if k == key:
                    return v

        raise KeyError(key)

    def __getitem__(self, key):
        return PMap._getitem(self._buckets, key)

    @staticmethod
    def _contains(buckets, key):
        _, bucket = PMap._get_bucket(buckets, key)
        if bucket:
            for k, _ in bucket:
                if k == key:
                    return True

            return False

        return False

    def __contains__(self, key):
        return self._contains(self._buckets, key)

    get = Mapping.get

    def __iter__(self):
        return self.iterkeys()

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError("PMap has no attribute '{0}'".format(key))

    def iterkeys(self):
        for k, _ in self.iteritems():
            yield k

    # These are more efficient implementations compared to the original
    # methods that are based on the keys iterator and then calls the
    # accessor functions to access the value for the corresponding key
    def itervalues(self):
        for _, v in self.iteritems():
            yield v

    def iteritems(self):
        for bucket in self._buckets:
            if bucket:
                for k, v in bucket:
                    yield k, v

    def values(self):
        return list(self.itervalues())

    def keys(self):
        return list(self.iterkeys())

    def items(self):
        return list(self.iteritems())

    def __len__(self):
        return self._size

    def __repr__(self):
        return 'pmap({0})'.format(str(dict(self)))

    __eq__ = Mapping.__eq__
    __ne__ = Mapping.__ne__

    def __str__(self):
        return self.__repr__()

    def __hash__(self):
        # This hashing algorithm is probably not the speediest
        return hash(frozenset(self.iteritems()))

    def set(self, key, val):
        """
        Return a new PMap with key and val inserted.

        >>> m1 = m(a=1, b=2)
        >>> m2 = m1.set('a', 3)
        >>> m3 = m1.set('c' ,4)
        >>> m1
        pmap({'a': 1, 'b': 2})
        >>> m2
        pmap({'a': 3, 'b': 2})
        >>> m3
        pmap({'a': 1, 'c': 4, 'b': 2})
        """
        return self.evolver().set(key, val).persistent()

    def remove(self, key):
        """
        Return a new PMap without the element specified by key. Raises KeyError if the element
        is not present.

        >>> m1 = m(a=1, b=2)
        >>> m1.remove('a')
        pmap({'b': 2})
        """
        return self.evolver().remove(key).persistent()

    def discard(self, key):
        """
        Return a new PMap without the element specified by key. Returns reference to itself
        if element is not present.

        >>> m1 = m(a=1, b=2)
        >>> m1.discard('a')
        pmap({'b': 2})
        >>> m1 is m1.discard('c')
        True
        """
        try:
            return self.remove(key)
        except KeyError:
            return self

    def update(self, *maps):
        """
        Return a new PMap with the items in Mappings inserted. If the same key is present in multiple
        maps the rightmost (last) value is inserted.

        >>> m1 = m(a=1, b=2)
        >>> m1.update(m(a=2, c=3), {'a': 17, 'd': 35})
        pmap({'a': 17, 'c': 3, 'b': 2, 'd': 35})
        """
        return self.update_with(lambda l, r: r, *maps)

    def update_with(self, update_fn, *maps):
        """
        Return a new PMap with the items in Mappings maps inserted. If the same key is present in multiple
        maps the values will be merged using merge_fn going from left to right.

        >>> from operator import add
        >>> m1 = m(a=1, b=2)
        >>> m1.update_with(add, m(a=2))
        pmap({'a': 3, 'b': 2})

        The reverse behaviour of the regular merge. Keep the leftmost element instead of the rightmost.

        >>> m1 = m(a=1)
        >>> m1.update_with(lambda l, r: l, m(a=2), {'a':3})
        pmap({'a': 1})
        """
        evolver = self.evolver()
        for map in maps:
            for key, value in map.items():
                evolver.set(key, update_fn(evolver[key], value) if key in evolver else value)

        return evolver.persistent()

    def set_in(self, keys, val):
        """
        Insert val into nested persistent structure at position specified by Iterable keys. Any levels that
        do not exist will be inserted as new PMaps.

        >>> m1 = m(a=5, b=6, c=v(1, 2))
        >>> m1.set_in(('c', 1), 17)
        pmap({'a': 5, 'c': pvector([1, 17]), 'b': 6})
        """
        import warnings
        warnings.warn("set_in is deprecated, use 467 instead", DeprecationWarning, stacklevel=2)
        return self.transform(keys, val)

    def __reduce__(self):
        # Pickling support
        return pmap, (dict(self),)

    def transform(self, *transformations):
        """
        Transform arbitrarily complex combinations of PVectors and PMaps. A transformation
        consists of two parts. One match expression that specifies which elements to transform
        and one transformation function that performs the actual transformation.

        >>> news_paper = freeze({'articles': [{'author': 'Sara', 'content': 'A short article'},
        ...                                   {'author': 'Steve', 'content': 'A slightly longer article'}],
        ...                      'weather': {'temperature': '11C', 'wind': '5m/s'}})
        >>> short_news = news_paper.transform(['articles', ny, 'content'], lambda c: c[:25] + '...' if len(c) > 25 else c)
        >>> very_short_news = news_paper.transform(['articles', ny, 'content'], lambda c: c[:15] + '...' if len(c) > 15 else c)
        >>> very_short_news.articles[0].content
        'A short article'
        >>> very_short_news.articles[1].content
        'A slightly long...'

        When nothing has been transformed the original data structure is kept

        >>> short_news is news_paper
        True
        >>> very_short_news is news_paper
        False
        >>> very_short_news.articles[0] is news_paper.articles[0]
        True
        """
        return _transform(self, transformations)

    def copy(self):
        return self

    class _Evolver(object):
        __slots__ = ('_buckets_evolver', '_size', '_original_pmap')

        def __init__(self, original_pmap):
            self._original_pmap = original_pmap
            self._buckets_evolver = original_pmap._buckets.evolver()
            self._size = original_pmap._size

        def __getitem__(self, key):
            return PMap._getitem(self._buckets_evolver, key)

        def __setitem__(self, key, val):
            self.set(key, val)

        def set(self, key, val):
            if len(self._buckets_evolver) < 0.67 * self._size:
                self._reallocate(2 * len(self._buckets_evolver))

            kv = (key, val)
            index, bucket = PMap._get_bucket(self._buckets_evolver, key)
            if bucket:
                for k, v in bucket:
                    if k == key:
                        if v is not val:
                            new_bucket = [(k2, v2) if k2 != k else (k2, val) for k2, v2 in bucket]
                            self._buckets_evolver[index] = new_bucket

                        return self

                new_bucket = [kv]
                new_bucket.extend(bucket)
                self._buckets_evolver[index] = new_bucket
                self._size += 1
            else:
                self._buckets_evolver[index] = [kv]
                self._size += 1

            return self

        def _reallocate(self, new_size):
            new_list = new_size * [None]
            buckets = self._buckets_evolver.persistent()
            for k, v in chain.from_iterable(x for x in buckets if x):
                index = hash(k) % new_size
                if new_list[index]:
                    new_list[index].append((k, v))
                else:
                    new_list[index] = [(k, v)]

            self._buckets_evolver = pvector().extend(new_list).evolver()

        def is_dirty(self):
            return self._buckets_evolver.is_dirty()

        def persistent(self):
            if self.is_dirty():
                return PMap(self._size, self._buckets_evolver.persistent())

            return self._original_pmap

        def __len__(self):
            return self._size

        def __contains__(self, key):
            return PMap._contains(self._buckets_evolver, key)

        def __delitem__(self, key):
            self.remove(key)

        def remove(self, key):
            index, bucket = PMap._get_bucket(self._buckets_evolver, key)

            if bucket:
                new_bucket = [(k, v) for (k, v) in bucket if k != key]
                if len(bucket) > len(new_bucket):
                    self._buckets_evolver[index] = new_bucket if new_bucket else None
                    self._size -= 1
                    return self

            raise KeyError('{0}'.format(key))

    def evolver(self):
        """
        Create a new evolver for this pmap. For a discussion on evolvers in general see the
        documentation for the pvector evolver.

        Create the evolver and perform various mutating updates to it:
        >>> m1 = m(a=1, b=2)
        >>> e = m1.evolver()
        >>> e['c'] = 3
        >>> len(e)
        3
        >>> del e['a']

        The underlying pmap remains the same:
        >>> m1
        pmap({'a': 1, 'b': 2})

        The changes are kept in the evolver. An updated pmap can be created using the
        pmap() function on the evolver.
        >>> m2 = e.persistent()
        >>> m2
        pmap({'c': 3, 'b': 2})

        The new pmap will share data with the original pmap in the same way that would have
        been done if only using operations on the pmap.
        """
        return self._Evolver(self)

Mapping.register(PMap)
Hashable.register(PMap)


def _turbo_mapping(initial, pre_size):
    size = pre_size or (2 * len(initial)) or 8
    buckets = size * [None]

    if not isinstance(initial, Mapping):
        # Make a dictionary of the initial data if it isn't already,
        # that will save us some job further down since we can assume no
        # key collisions
        initial = dict(initial)

    for k, v in six.iteritems(initial):
        h = hash(k)
        index = h % size
        bucket = buckets[index]

        if bucket:
            bucket.append((k, v))
        else:
            buckets[index] = [(k, v)]

    return PMap(len(initial), _EMPTY_PVECTOR.extend(buckets))


_EMPTY_PMAP = _turbo_mapping({}, 0)


def pmap(initial={}, pre_size=0):
    """
    Create new persistent map, inserts all elements in initial into the newly created map.
    The optional argument pre_size may be used to specify an initial size of the underlying bucket vector. This
    may have a positive performance impact in the cases where you know beforehand that a large number of elements
    will be inserted into the map eventually since it will reduce the number of reallocations required.

    >>> pmap({'a': 13, 'b': 14})
    pmap({'a': 13, 'b': 14})
    """
    if not initial:
        return _EMPTY_PMAP

    return _turbo_mapping(initial, pre_size)


def m(**kwargs):
    """
    Creates a new persitent map. Inserts all key value arguments into the newly created map.

    >>> m(a=13, b=14)
    pmap({'a': 13, 'b': 14})
    """
    return pmap(kwargs)

##################### PSet ########################


PY2 = sys.version_info[0] < 3


class PSet(object):
    """
    Persistent set implementation. Built on top of the persistent map. The set supports all operations
    in the Set protocol and is Hashable.

    Do not instantiate directly, instead use the factory functions :py:func:`s` or :py:func:`pset`
    to create an instance.

    Random access and insert is log32(n) where n is the size of the set.

    Some examples:

    >>> s = pset([1, 2, 3, 1])
    >>> s2 = s.add(4)
    >>> s3 = s2.remove(2)
    >>> s
    pset([1, 2, 3])
    >>> s2
    pset([1, 2, 3, 4])
    >>> s3
    pset([1, 3, 4])
    """
    __slots__ = ('_map',)

    def __new__(cls, m):
        self = super(PSet, cls).__new__(cls)
        self._map = m
        return self

    def __contains__(self, element):
        return element in self._map

    def __iter__(self):
        return iter(self._map)

    def __len__(self):
        return len(self._map)

    def __repr__(self):
        if PY2 or not self:
            return 'p' + str(set(self))

        return 'pset([{0}])'.format(str(set(self))[1:-1])

    def __str__(self):
        return self.__repr__()

    def __hash__(self):
        return hash(self._map)

    def __reduce__(self):
        # Pickling support
        return pset, (list(self),)

    @classmethod
    def _from_iterable(cls, it, pre_size=8):
        return PSet(pmap(dict((k, True) for k in it), pre_size=pre_size))

    def add(self, element):
        """
        Return a new PSet with element added

        >>> s1 = s(1, 2)
        >>> s1.add(3)
        pset([1, 2, 3])
        """
        return self.evolver().add(element).persistent()

    def remove(self, element):
        """
        Return a new PSet with element removed. Raises KeyError if element is not present.

        >>> s1 = s(1, 2)
        >>> s1.remove(2)
        pset([1])
        """
        if element in self._map:
            return self.evolver().remove(element).persistent()

        raise KeyError("Element '%s' not present in PSet" % element)

    def discard(self, element):
        """
        Return a new PSet with element removed. Returns itself if element is not present.
        """
        if element in self._map:
            return self.evolver().remove(element).persistent()

        return self

    class _Evolver(object):
        __slots__ = ('_original_pset', '_pmap_evolver')

        def __init__(self, original_pset):
            self._original_pset = original_pset
            self._pmap_evolver = original_pset._map.evolver()

        def add(self, element):
            self._pmap_evolver[element] = True
            return self

        def remove(self, element):
            del self._pmap_evolver[element]
            return self

        def is_dirty(self):
            return self._pmap_evolver.is_dirty()

        def persistent(self):
            if not self.is_dirty():
                return  self._original_pset

            return PSet(self._pmap_evolver.persistent())

        def __len__(self):
            return len(self._pmap_evolver)

    def copy(self):
        return self

    def evolver(self):
        """
        Create a new evolver for this pset. For a discussion on evolvers in general see the
        documentation for the pvector evolver.

        Create the evolver and perform various mutating updates to it:
        >>> s1 = s(1, 2, 3)
        >>> e = s1.evolver()
        >>> _ = e.add(4)
        >>> len(e)
        4
        >>> _ = e.remove(1)

        The underlying pset remains the same:
        >>> s1
        pset([1, 2, 3])

        The changes are kept in the evolver. An updated pmap can be created using the
        pset() function on the evolver.
        >>> s2 = e.persistent()
        >>> s2
        pset([2, 3, 4])

        The new pset will share data with the original pset in the same way that would have
        been done if only using operations on the pset.
        """
        return PSet._Evolver(self)

    # All the operations and comparisons you would expect on a set.
    #
    # This is not very beautiful. If we avoid inheriting from PSet we can use the
    # __slots__ concepts (which requires a new style class) and hopefully save some memory.
    __le__ = Set.__le__
    __lt__ = Set.__lt__
    __gt__ = Set.__gt__
    __ge__ = Set.__ge__
    __eq__ = Set.__eq__
    __ne__ = Set.__ne__

    __and__ = Set.__and__
    __or__ = Set.__or__
    __sub__ = Set.__sub__
    __xor__ = Set.__xor__

    issubset = __le__
    issuperset = __ge__
    union = __or__
    intersection = __and__
    difference = __sub__
    symmetric_difference = __xor__

    isdisjoint = Set.isdisjoint

Set.register(PSet)
Hashable.register(PSet)

_EMPTY_PSET = PSet(_EMPTY_PMAP)


def pset(iterable=(), pre_size=8):
    """
    Creates a persistent set from iterable. Optionally takes a sizing parameter equivalent to that
    used for :py:func:`pmap`.

    >>> s1 = pset([1, 2, 3, 2])
    >>> s1
    pset([1, 2, 3])
    """
    if not iterable:
        return _EMPTY_PSET

    return PSet._from_iterable(iterable, pre_size=pre_size)


def s(*elements):
    """
    Create a persistent set.

    Takes an arbitrary number of arguments to insert into the new set.

    >>> s1 = s(1, 2, 3, 2)
    >>> s1
    pset([1, 2, 3])
    """
    return pset(elements)


##################### PBag ########################


def _add_to_counters(counters, element):
    return counters.set(element, counters.get(element, 0) + 1)


class _PBag(object):
    """
    A persistent bag/multiset type.

    Requires elements to be hashable, and allows duplicates, but has no
    ordering. Bags are hashable.

    Do not instantiate directly, instead use the factory functions :py:func:`b`
    or :py:func:`pbag` to create an instance.

    Some examples:

    >>> s = pbag([1, 2, 3, 1])
    >>> s2 = s.add(4)
    >>> s3 = s2.remove(1)
    >>> s
    pbag([1, 1, 2, 3])
    >>> s2
    pbag([1, 1, 2, 3, 4])
    >>> s3
    pbag([1, 2, 3, 4])
    """

    __slots__ = ('_counts',)

    def __init__(self, counts):
        self._counts = counts

    def add(self, element):
        """
        Add an element to the bag.

        >>> s = pbag([1])
        >>> s2 = s.add(1)
        >>> s3 = s.add(2)
        >>> s2
        pbag([1, 1])
        >>> s3
        pbag([1, 2])
        """
        return _PBag(_add_to_counters(self._counts, element))

    def remove(self, element):
        """
        Remove an element from the bag.

        >>> s = pbag([1, 1, 2])
        >>> s2 = s.remove(1)
        >>> s3 = s.remove(2)
        >>> s2
        pbag([1, 2])
        >>> s3
        pbag([1, 1])
        """
        if element not in self._counts:
            raise KeyError(element)
        elif self._counts[element] == 1:
            newc = self._counts.remove(element)
        else:
            newc = self._counts.set(element, self._counts[element] - 1)
        return _PBag(newc)

    def count(self, element):
        """
        Return the number of times an element appears.


        >>> pbag([]).count('non-existent')
        0
        >>> pbag([1, 1, 2]).count(1)
        2
        """
        return self._counts.get(element, 0)

    def __len__(self):
        """
        Return the length including duplicates.

        >>> len(pbag([1, 1, 2]))
        3
        """
        return sum(self._counts.itervalues())

    def __iter__(self):
        """
        Return an iterator of all elements, including duplicates.

        >>> list(pbag([1, 1, 2]))
        [1, 1, 2]
        >>> list(pbag([1, 2]))
        [1, 2]
        """
        for elt, count in self._counts.iteritems():
            for i in range(count):
                yield elt

    def __contains__(self, elt):
        """
        Check if an element is in the bag.

        >>> 1 in pbag([1, 1, 2])
        True
        >>> 0 in pbag([1, 2])
        False
        """
        return elt in self._counts

    def __repr__(self):
        return "pbag({0})".format(list(self))

    def __eq__(self, other):
        """
        Check if two bags are equivalent, honoring the number of duplicates,
        and ignoring insertion order.

        >>> pbag([1, 1, 2]) == pbag([1, 2])
        False
        >>> pbag([2, 1, 0]) == pbag([0, 1, 2])
        True
        """
        if type(other) is not _PBag:
            raise TypeError("Can only compare PBag with PBags")
        return self._counts == other._counts

    def __hash__(self):
        """
        Hash based on value of elements.

        >>> m = pmap({pbag([1, 2]): "it's here!"})
        >>> m[pbag([2, 1])]
        "it's here!"
        >>> pbag([1, 1, 2]) in m
        False
        """
        return hash(self._counts)


Container.register(_PBag)
Iterable.register(_PBag)
Sized.register(_PBag)
Hashable.register(_PBag)


def b(*elements):
    """
    Construct a persistent bag.

    Takes an arbitrary number of arguments to insert into the new persistent
    bag.

    >>> b(1, 2, 3, 2)
    pbag([1, 2, 2, 3])
    """
    return pbag(elements)


def pbag(elements):
    """
    Convert an iterable to a persistent bag.

    Takes an iterable with elements to insert.

    >>> pbag([1, 2, 3, 2])
    pbag([1, 2, 2, 3])
    """
    if not elements:
        return _EMPTY_PBAG
    return _PBag(reduce(_add_to_counters, elements, m()))


_EMPTY_PBAG = _PBag(_EMPTY_PMAP)


######################################## Immutable object ##############################################

def pclass(members='', name='PClass', verbose=False):
    """
    Produces a class that either can be used standalone or as a base class for persistent classes.

    This is a thin wrapper around a named tuple.

    Constructing a type and using it to instantiate objects:

    >>> Point = pclass('x, y', name='Point')
    >>> p = Point(1, 2)
    >>> p2 = p.set(x=3)
    >>> p
    Point(x=1, y=2)
    >>> p2
    Point(x=3, y=2)

    Inheriting from a constructed type. In this case no type name needs to be supplied:

    >>> class PositivePoint(pclass('x, y')):
    ...     __slots__ = tuple()
    ...     def __new__(cls, x, y):
    ...         if x > 0 and y > 0:
    ...             return super(PositivePoint, cls).__new__(cls, x, y)
    ...         raise Exception('Coordinates must be positive!')
    ...
    >>> p = PositivePoint(1, 2)
    >>> p.set(x=3)
    PositivePoint(x=3, y=2)
    >>> p.set(y=-3)
    Traceback (most recent call last):
    Exception: Coordinates must be positive!

    The persistent class also supports the notion of frozen members. The value of a frozen member
    cannot be updated. For example it could be used to implement an ID that should remain the same
    over time. A frozen member is denoted by a trailing underscore.

    >>> Point = pclass('x, y, id_', name='Point')
    >>> p = Point(1, 2, id_=17)
    >>> p.set(x=3)
    Point(x=3, y=2, id_=17)
    >>> p.set(id_=18)
    Traceback (most recent call last):
    AttributeError: Cannot set frozen members id_
    """

    if isinstance(members, six.string_types):
        members = members.replace(',', ' ').split()

    def frozen_member_test():
        frozen_members = ["'%s'" % f for f in members if f.endswith('_')]
        if frozen_members:
            return """
        frozen_fields = fields_to_modify & set([{frozen_members}])
        if frozen_fields:
            raise AttributeError('Cannot set frozen members %s' % ', '.join(frozen_fields))
            """.format(frozen_members=', '.join(frozen_members))

        return ''

    quoted_members = ', '.join("'%s'" % m for m in members)
    template = """
class {class_name}(namedtuple('PClassBase', [{quoted_members}], verbose={verbose})):
    __slots__ = tuple()

    def __repr__(self):
        return super({class_name}, self).__repr__().replace('PClassBase', self.__class__.__name__)

    def set(self, **kwargs):
        if not kwargs:
            return self

        fields_to_modify = set(kwargs.keys())
        if not fields_to_modify <= {member_set}:
            raise AttributeError("'%s' is not a member" % ', '.join(fields_to_modify - {member_set}))

        {frozen_member_test}

        return self.__class__.__new__(self.__class__, *map(kwargs.pop, [{quoted_members}], self))
""".format(quoted_members=quoted_members,
               member_set="set([%s])" % quoted_members if quoted_members else 'set()',
               frozen_member_test=frozen_member_test(),
               verbose=verbose,
               class_name=name)

    if verbose:
        print(template)

    from collections import namedtuple
    namespace = dict(namedtuple=namedtuple, __name__='pyrsistent_pclass')
    try:
        six.exec_(template, namespace)
    except SyntaxError as e:
        raise SyntaxError(e.message + ':\n' + template)

    return namespace[name]

## Freeze & Thaw

def freeze(o):
    """
    Recursively convert simple Python containers into pyrsistent versions
    of those containers.

    - list is converted to pvector, recursively
    - dict is converted to pmap, recursively on values (but not keys)
    - set is converted to pset, but not recursively
    - tuple is converted to tuple, recursively.

    Sets and dict keys are not recursively frozen because they do not contain
    mutable data by convention. The main exception to this rule is that
    dict keys and set elements are often instances of mutable objects that
    support hash-by-id, which this function can't convert anyway.

    >>> freeze(set([1, 2]))
    pset([1, 2])
    >>> freeze([1, {'a': 3}])
    pvector([1, pmap({'a': 3})])
    >>> freeze((1, []))
    (1, pvector([]))
    """
    typ = type(o)
    if typ is dict:
        return pmap(dict((k, freeze(v)) for k, v in six.iteritems(o)))
    if typ is list:
        return pvector(map(freeze, o))
    if typ is tuple:
        return tuple(map(freeze, o))
    if typ is set:
        return pset(o)
    return o


def thaw(o):
    """
    Recursively convert pyrsistent containers into simple Python containers.

    - pvector is converted to list, recursively
    - pmap is converted to dict, recursively on values (but not keys)
    - pset is converted to set, but not recursively
    - tuple is converted to tuple, recursively.

    >>> thaw(s(1, 2))
    set([1, 2])
    >>> thaw(v(1, m(a=3)))
    [1, {'a': 3}]
    >>> thaw((1, v()))
    (1, [])
    """
    if isinstance(o, PVector):
        return list(map(thaw, o))
    if isinstance(o, PMap):
        return dict((k, thaw(v)) for k, v in o.iteritems())
    if isinstance(o, PSet):
        return set(o)
    if type(o) is tuple:
        return tuple(map(thaw, o))
    return o


def mutant(fn):
    """
    Convenience decorator to isolate mutation to within the decorated function (with respect
    to the input arguments).

    All arguments to the decorated function will be frozen so that they are guaranteed not to change.
    The return value is also frozen.
    """
    @wraps(fn)
    def inner_f(*args, **kwargs):
        return freeze(fn(*[freeze(e) for e in args], **dict(freeze(item) for item in kwargs.items())))

    return inner_f


##### PList ####

class _PListBuilder(object):
    """
    Helper class to allow construction of a list without
    having to reverse it in the end.
    """
    __slots__ = ('_head', '_tail')

    def __init__(self):
        self._head = _EMPTY_PLIST
        self._tail = _EMPTY_PLIST

    def _append(self, elem, constructor):
        if not self._tail:
            self._head = constructor(elem)
            self._tail = self._head
        else:
            self._tail.rest = constructor(elem)
            self._tail = self._tail.rest

        return self._head

    def append_elem(self, elem):
        return self._append(elem, lambda e: _PList(e, _EMPTY_PLIST))

    def append_plist(self, pl):
        return self._append(pl, lambda l: l)

    def build(self):
        return self._head


class _PListBase(object):
    __slots__ = ()

    # Selected implementations can be taken straight from the Sequence
    # class, other are less suitable. Especially those that work with
    # index lookups.
    count = Sequence.count
    index = Sequence.index

    def __reduce__(self):
        # Pickling support
        return plist, (list(self),)

    def __len__(self):
        # This is obviously O(n) but with the current implementation
        # where a list is also a node the overhead of storing the length
        # in every node would be quite significant.
        return sum(1 for _ in self)

    def __repr__(self):
        return "plist({0})".format(list(self))
    __str__ = __repr__

    def cons(self, elem):
        """
        Return a new list with elem inserted as new head.

        >>> plist([1, 2]).cons(3)
        plist([3, 1, 2])
        """
        return _PList(elem, self)

    def mcons(self, iterable):
        """
        Return a new list with all elements of iterable repeatedly cons:ed to the current list.
        NB! The elements will be inserted in the reverse order of the iterable.
        Runs in O(len(iterable)).

        >>> plist([1, 2]).mcons([3, 4])
        plist([4, 3, 1, 2])
        """
        head = self
        for elem in iterable:
            head = head.cons(elem)

        return head

    def reverse(self):
        """
        Return a reversed version of list. Runs in O(n) where n is the length of the list.

        >>> plist([1, 2, 3]).reverse()
        plist([3, 2, 1])

        Also supports the standard reversed function.

        >>> reversed(plist([1, 2, 3]))
        plist([3, 2, 1])
        """
        result = plist()
        head = self
        while head:
            result = result.cons(head.first)
            head = head.rest

        return result
    __reversed__ = reverse

    def split(self, index):
        """
        Spilt the list at position specified by index. Returns a tuple containing the
        list up until index and the list after the index. Runs in O(index).

        >>> plist([1, 2, 3, 4]).split(2)
        (plist([1, 2]), plist([3, 4]))
        """
        lb = _PListBuilder()
        right_list = self
        i = 0
        while right_list and i < index:
            lb.append_elem(right_list.first)
            right_list = right_list.rest
            i += 1

        if not right_list:
            # Just a small optimization in the cases where no split occurred
            return self, _EMPTY_PLIST

        return lb.build(), right_list

    def __iter__(self):
        li = self
        while li:
            yield li.first
            li = li.rest

    def __lt__(self, other):
        if not isinstance(other, _PListBase):
            return NotImplemented

        return tuple(self) < tuple(other)

    def __eq__(self, other):
        if not isinstance(other, _PListBase):
            return NotImplemented

        self_head = self
        other_head = other
        while self_head and other_head:
            if not self_head.first == other_head.first:
                return False
            self_head = self_head.rest
            other_head = other_head.rest

        return not self_head and not other_head

    def __getitem__(self, index):
        # Don't use this this data structure if you plan to do a lot of indexing, it is
        # very inefficient! Use a PVector instead!

        if isinstance(index, slice):
            if index.start is not None and index.stop is None and (index.step is None or index.step == 1):
                return self._drop(index.start)

            # Take the easy way out for all other slicing cases, not much structural reuse possible anyway
            return plist(tuple(self)[index])

        if not isinstance(index, Integral):
            raise TypeError("'%s' object cannot be interpreted as an index" % type(index).__name__)

        if index < 0:
            # NB: O(n)!
            index += len(self)

        try:
            return self._drop(index).first
        except AttributeError:
            raise IndexError("PList index out of range")

    def _drop(self, count):
        if count < 0:
            raise IndexError("PList index out of range")

        head = self
        while count > 0:
            head = head.rest
            count -= 1

        return head

    def __hash__(self):
        return hash(tuple(self))

    def remove(self, elem):
        """
        Return new list with first element equal to elem removed. O(k) where k is the position
        of the element that is removed.

        Raises ValueError if no matching element is found.

        >>> plist([1, 2, 1]).remove(1)
        plist([2, 1])
        """

        builder = _PListBuilder()
        head = self
        while head:
            if head.first == elem:
                return builder.append_plist(head.rest)

            builder.append_elem(head.first)
            head = head.rest

        raise ValueError('{0} not found in PList'.format(elem))


class _PList(_PListBase):
    """
    Classical Lisp style singly linked list. Adding elements to the head using cons is O(1).
    Element access is O(k) where k is the position of the element in the list. Taking the
    length of the list is O(n).

    Fully supports the Sequence and Hashable protocols including indexing and slicing but
    if you need fast random access go for the PVector instead.

    Do not instantiate directly, instead use the factory functions :py:func:`l` or :py:func:`plist` to
    create an instance.

    Some examples:

    >>> x = plist([1, 2])
    >>> y = x.cons(3)
    >>> x
    plist([1, 2])
    >>> y
    plist([3, 1, 2])
    >>> y.first
    3
    >>> y.rest == x
    True
    >>> y[:2]
    plist([3, 1])
    """
    __slots__ = ('first', 'rest')

    def __new__(cls, first, rest):
        instance = super(_PList, cls).__new__(cls)
        instance.first = first
        instance.rest = rest
        return instance

    def __bool__(self):
        return True
    __nonzero__ = __bool__


Sequence.register(_PList)
Hashable.register(_PList)


class _EmptyPList(_PListBase):
    __slots__ = ()

    def __bool__(self):
        return False
    __nonzero__ = __bool__

    @property
    def first(self):
        raise AttributeError("Empty PList has no first")

    @property
    def rest(self):
        return self


Sequence.register(_EmptyPList)
Hashable.register(_EmptyPList)

_EMPTY_PLIST = _EmptyPList()

def plist(iterable=(), reverse=False):
    """
    Creates a new persistent list containing all elements of iterable.
    Optional parameter reverse specifies if the elements should be inserted in
    reverse order or not.

    >>> plist([1, 2, 3])
    plist([1, 2, 3])
    >>> plist([1, 2, 3], reverse=True)
    plist([3, 2, 1])
    """
    if not reverse:
        iterable = list(iterable)
        iterable.reverse()

    return reduce(lambda pl, elem: pl.cons(elem), iterable, _EMPTY_PLIST)


def l(*elements):
    """
    Creates a new persistent list containing all arguments.

    >>> l(1, 2, 3)
    plist([1, 2, 3])
    """
    return plist(elements)

##### PDeque #####
class _PDeque(object):
    """
    Persistent double ended queue (deque). Allows quick appends and pops in both ends. Implemented
    using two persistent lists.

    A maximum length can be specified to create a bounded queue.

    Fully supports the Sequence and Hashable protocols including indexing and slicing but
    if you need fast random access go for the PVector instead.

    Do not instantiate directly, instead use the factory functions :py:func:`dq` or :py:func:`pdeque` to
    create an instance.

    Some examples:

    >>> x = pdeque([1, 2, 3])
    >>> x.left
    1
    >>> x.right
    3
    >>> x[0] == x.left
    True
    >>> x[-1] == x.right
    True
    >>> x.pop()
    pdeque([1, 2])
    >>> x.pop() == x[:-1]
    True
    >>> x.popleft()
    pdeque([2, 3])
    >>> x.append(4)
    pdeque([1, 2, 3, 4])
    >>> x.appendleft(4)
    pdeque([4, 1, 2, 3])

    >>> y = pdeque([1, 2, 3], maxlen=3)
    >>> y.append(4)
    pdeque([2, 3, 4], maxlen=3)
    >>> y.appendleft(4)
    pdeque([4, 1, 2], maxlen=3)
    """
    __slots__ = ('_left_list', '_right_list', '_length', '_maxlen')

    def __new__(cls, left_list, right_list, length, maxlen=None):
        instance = super(_PDeque, cls).__new__(cls)
        instance._left_list = left_list
        instance._right_list = right_list
        instance._length = length

        if maxlen is not None:
            if not isinstance(maxlen, Integral):
                raise TypeError('An integer is required as maxlen')

            if maxlen < 0:
                raise ValueError("maxlen must be non-negative")

        instance._maxlen = maxlen
        return instance

    @property
    def right(self):
        """
        Rightmost element in dqueue.
        """
        return _PDeque._tip_from_lists(self._right_list, self._left_list)

    @property
    def left(self):
        """
        Leftmost element in dqueue.
        """
        return _PDeque._tip_from_lists(self._left_list, self._right_list)

    @staticmethod
    def _tip_from_lists(primary_list, secondary_list):
        if primary_list:
            return primary_list.first

        if secondary_list:
            return secondary_list[-1]

        raise IndexError('No elements in empty deque')

    def __iter__(self):
        return chain(self._left_list, self._right_list.reverse())

    def __repr__(self):
        return "pdeque({0}{1})".format(list(self),
                                       ', maxlen={0}'.format(self._maxlen) if self._maxlen is not None else '')
    __str__ = __repr__

    @property
    def maxlen(self):
        """
        Maximum length of the queue.
        """
        return self._maxlen

    def pop(self, count=1):
        """
        Return new deque with rightmost element removed. Popping the empty queue
        will return the empty queue. A optional count can be given to indicate the
        number of elements to pop. Popping with a negative index is the same as
        popleft. Executes in amortized O(k) where k is the number of elements to pop.

        >>> pdeque([1, 2]).pop()
        pdeque([1])
        >>> pdeque([1, 2]).pop(2)
        pdeque([])
        >>> pdeque([1, 2]).pop(-1)
        pdeque([2])
        """
        if count < 0:
            return self.popleft(-count)

        new_right_list, new_left_list = _PDeque._pop_lists(self._right_list, self._left_list, count)
        return _PDeque(new_left_list, new_right_list, max(self._length - count, 0), self._maxlen)

    def popleft(self, count=1):
        """
        Return new deque with leftmost element removed. Otherwise functionally
        equivalent to pop().

        >>> pdeque([1, 2]).popleft()
        pdeque([2])
        """
        if count < 0:
            return self.pop(-count)

        new_left_list, new_right_list = _PDeque._pop_lists(self._left_list, self._right_list, count)
        return _PDeque(new_left_list, new_right_list, max(self._length - count, 0), self._maxlen)

    @staticmethod
    def _pop_lists(primary_list, secondary_list, count):
        new_primary_list = primary_list
        new_secondary_list = secondary_list

        while count > 0 and (new_primary_list or new_secondary_list):
            count -= 1
            if new_primary_list.rest:
                new_primary_list = new_primary_list.rest
            elif new_primary_list:
                new_primary_list = new_secondary_list.reverse()
                new_secondary_list = _EMPTY_PLIST
            else:
                new_primary_list = new_secondary_list.reverse().rest
                new_secondary_list = _EMPTY_PLIST

        return new_primary_list, new_secondary_list

    def _is_empty(self):
        return not self._left_list and not self._right_list

    def __lt__(self, other):
        if not isinstance(other, _PDeque):
            return NotImplemented

        return tuple(self) < tuple(other)

    def __eq__(self, other):
        if not isinstance(other, _PDeque):
            return NotImplemented

        if tuple(self) == tuple(other):
            # Sanity check of the length value since it is redundant (there for performance)
            assert len(self) == len(other)
            return True

        return False

    def __hash__(self):
        return  hash(tuple(self))

    def __len__(self):
        return self._length

    def append(self, elem):
        """
        Return new deque with elem as the rightmost element.

        >>> pdeque([1, 2]).append(3)
        pdeque([1, 2, 3])
        """
        new_left_list, new_right_list, new_length = self._append(self._left_list, self._right_list, elem)
        return _PDeque(new_left_list, new_right_list, new_length, self._maxlen)

    def appendleft(self, elem):
        """
        Return new deque with elem as the leftmost element.

        >>> pdeque([1, 2]).appendleft(3)
        pdeque([3, 1, 2])
        """
        new_right_list, new_left_list, new_length = self._append(self._right_list, self._left_list, elem)
        return _PDeque(new_left_list, new_right_list, new_length, self._maxlen)

    def _append(self, primary_list, secondary_list, elem):
        if self._maxlen is not None and self._length == self._maxlen:
            if self._maxlen == 0:
                return primary_list, secondary_list, 0
            new_primary_list, new_secondary_list = _PDeque._pop_lists(primary_list, secondary_list, 1)
            return new_primary_list, new_secondary_list.cons(elem), self._length

        return primary_list, secondary_list.cons(elem), self._length + 1

    @staticmethod
    def _extend_list(the_list, iterable):
        count = 0
        for elem in iterable:
            the_list = the_list.cons(elem)
            count += 1

        return the_list, count

    def _extend(self, primary_list, secondary_list, iterable):
        new_primary_list, extend_count = _PDeque._extend_list(primary_list, iterable)
        new_secondary_list = secondary_list
        current_len = self._length + extend_count
        if self._maxlen is not None and current_len > self._maxlen:
            pop_len = current_len - self._maxlen
            new_secondary_list, new_primary_list = _PDeque._pop_lists(new_secondary_list, new_primary_list, pop_len)
            extend_count -= pop_len

        return new_primary_list, new_secondary_list, extend_count

    def extend(self, iterable):
        """
        Return new deque with all elements of iterable appended to the right.

        >>> pdeque([1, 2]).extend([3, 4])
        pdeque([1, 2, 3, 4])
        """
        new_right_list, new_left_list, extend_count = self._extend(self._right_list, self._left_list, iterable)
        return _PDeque(new_left_list, new_right_list, self._length + extend_count, self._maxlen)

    def extendleft(self, iterable):
        """
        Return new deque with all elements of iterable appended to the left.

        NB! The elements will be inserted in reverse order compared to the order in the iterable.

        >>> pdeque([1, 2]).extendleft([3, 4])
        pdeque([4, 3, 1, 2])
        """
        new_left_list, new_right_list, extend_count = self._extend(self._left_list, self._right_list, iterable)
        return _PDeque(new_left_list, new_right_list, self._length + extend_count, self._maxlen)

    def count(self, elem):
        """
        Return the number of elements equal to elem present in the queue

        >>> pdeque([1, 2, 1]).count(1)
        2
        """
        return self._left_list.count(elem) + self._right_list.count(elem)

    def remove(self, elem):
        """
        Return new deque with first element from left equal to elem removed. If no such element is found
        a ValueError is raised.

        >>> pdeque([2, 1, 2]).remove(2)
        pdeque([1, 2])
        """
        try:
            return _PDeque(self._left_list.remove(elem), self._right_list, self._length - 1)
        except ValueError:
            # Value not found in left list, try the right list
            try:
                # This is severely inefficient with a double reverse, should perhaps implement a remove_last()?
                return _PDeque(self._left_list,
                               self._right_list.reverse().remove(elem).reverse(), self._length - 1)
            except ValueError:
                raise ValueError('{0} not found in PDeque'.format(elem))

    def reverse(self):
        """
        Return reversed deque.

        >>> pdeque([1, 2, 3]).reverse()
        pdeque([3, 2, 1])

        Also supports the standard python reverse function.

        >>> reversed(pdeque([1, 2, 3]))
        pdeque([3, 2, 1])
        """
        return _PDeque(self._right_list, self._left_list, self._length)
    __reversed__ = reverse

    def rotate(self, steps):
        """
        Return deque with elements rotated steps steps.

        >>> x = pdeque([1, 2, 3])
        >>> x.rotate(1)
        pdeque([3, 1, 2])
        >>> x.rotate(-2)
        pdeque([3, 1, 2])
        """
        popped_deque = self.pop(steps)
        if steps >= 0:
            return popped_deque.extendleft(islice(self.reverse(), steps))

        return popped_deque.extend(islice(self, -steps))

    def __reduce__(self):
        # Pickling support
        return pdeque, (list(self), self._maxlen)

    def __getitem__(self, index):
        if isinstance(index, slice):
            if index.step is not None and index.step != 1:
                # Too difficult, no structural sharing possible
                return pdeque(tuple(self)[index], maxlen=self._maxlen)

            result = self
            if index.start is not None:
                result = result.popleft(index.start % self._length)
            if index.stop is not None:
                result = result.pop(self._length - (index.stop % self._length))

            return result

        if not isinstance(index, Integral):
            raise TypeError("'%s' object cannot be interpreted as an index" % type(index).__name__)

        if index >= 0:
            return self.popleft(index).left

        return  self.pop(index).right

    index = Sequence.index

Sequence.register(_PDeque)
Hashable.register(_PDeque)


def pdeque(iterable=(), maxlen=None):
    """
    Return deque containing the elements of iterable. If maxlen is specified then
    len(iterable) - maxlen elements are discarded from the left to if len(iterable) > maxlen.

    >>> pdeque([1, 2, 3])
    pdeque([1, 2, 3])
    >>> pdeque([1, 2, 3, 4], maxlen=2)
    pdeque([3, 4], maxlen=2)
    """
    t = tuple(iterable)
    if maxlen is not None:
        t = t[-maxlen:]
    length = len(t)
    pivot = int(length / 2)
    left = plist(t[:pivot])
    right = plist(t[pivot:], reverse=True)
    return _PDeque(left, right, length, maxlen)

def dq(*elements):
    """
    Return deque containing all arguments.

    >>> dq(1, 2, 3)
    pdeque([1, 2, 3])
    """
    return pdeque(elements)


###### PRecord ######

class _PRecordMeta(type):
    def __new__(mcs, name, bases, dct):
        dct['_precord_fields'] = dict(sum([list(b.__dict__.get('_precord_fields', {}).items()) for b in bases], []))

        for k, v in list(dct.items()):
            if isinstance(v, _PRecordField):
                dct['_precord_fields'][k] = v
                del dct[k]

        # Global invariants are inherited
        dct['_precord_invariants'] = [dct['__invariant__']] if '__invariant__' in dct else []
        dct['_precord_invariants'] += [b.__dict__['__invariant__'] for b in bases if '__invariant__' in b.__dict__]
        if not all(callable(invariant) for invariant in dct['_precord_invariants']):
            raise TypeError('Global invariants must be callable')

        dct['_precord_mandatory_fields'] = \
            set(name for name, field in dct['_precord_fields'].items() if field.mandatory)

        dct['_precord_initial_values'] = \
            dict((k, field.initial) for k, field in dct['_precord_fields'].items() if field.initial is not _PRECORD_NO_INITIAL)

        dct['__slots__'] = ()

        return super(_PRecordMeta, mcs).__new__(mcs, name, bases, dct)


class InvariantException(Exception):
    """
    Exception raised from :py:class:`PRecord` when invariant tests fail or when a mandatory
    field is missing.

    Contains two fields of interest:
    invariant_errors, a tuple of error data for the failing invariants
    missing_fields, a tuple of strings specifying the missing names
    """

    def __init__(self, error_codes=(), missing_fields=(), *args, **kwargs):
        self.invariant_errors = error_codes
        self.missing_fields = missing_fields
        super(InvariantException, self).__init__(*args, **kwargs)

class _PRecordField(object):
    __slots__ = ('type', 'invariant', 'initial', 'mandatory', 'factory', 'serializer')

    def __init__(self, type, invariant, initial, mandatory, factory, serializer):
        self.type = type
        self.invariant = invariant
        self.initial = initial
        self.mandatory = mandatory
        self.factory = factory
        self.serializer = serializer

_PRECORD_NO_TYPE = ()
_PRECORD_NO_INVARIANT = lambda _: (True, None)
_PRECORD_NO_FACTORY = lambda x: x
_PRECORD_NO_INITIAL = object()
_PRECORD_NO_SERIALIZER = lambda _, value: value

def field(type=_PRECORD_NO_TYPE, invariant=_PRECORD_NO_INVARIANT, initial=_PRECORD_NO_INITIAL,
          mandatory=False, factory=_PRECORD_NO_FACTORY, serializer=_PRECORD_NO_SERIALIZER):
    """
    Field specification factory for :py:class:`PRecord`.

    :param type: a type or iterable with types that are allowed for this field
    :param invariant: a function specifying an invariant that must hold for the field
    :param initial: value of field if not specified when instantiating the record
    :param mandatorty: boolean specifying if the field is mandatory or not
    :param factory: function called when field is set.
    :param serializer: function that returns a serialized version of the field
    """

    types = set(type) if isinstance(type, Iterable) else set([type])

    # If no factory is specified and the type is another CheckedType use the factory method of that CheckedType
    if factory is _PRECORD_NO_FACTORY and len(types) == 1 and issubclass(tuple(types)[0], CheckedType):
        # TODO: Should this option be looked up at execution time rather than at field construction time?
        #       that would allow checking against all the types specified and if none matches the
        #       first
        factory = tuple(types)[0].create

    field = _PRecordField(type=types, invariant=invariant, initial=initial, mandatory=mandatory,
                          factory=factory, serializer=serializer)

    _check_field_parameters(field)

    return field

def _check_field_parameters(field):
    for t in field.type:
        if not isinstance(t, type):
            raise TypeError('Type paramenter expected, not {0}'.format(type(t)))

    if field.initial is not _PRECORD_NO_INITIAL and field.type and not any(isinstance(field.initial, t) for t in field.type):
        raise TypeError('Initial has invalid type {0}'.format(type(t)))

    if not callable(field.invariant):
        raise TypeError('Invariant must be callable')

    if not callable(field.factory):
        raise TypeError('Factory must be callable')

    if not callable(field.serializer):
        raise TypeError('Serializer must be callable')

def _restore_pickle(cls, data):
    return cls.create(data)

class CheckedType(object):
    __slots__ = ()

    @classmethod
    def create(cls, source_data):
        raise NotImplementedError()

    def serialize(self, format=None):
        raise NotImplementedError()

@six.add_metaclass(_PRecordMeta)
class PRecord(PMap, CheckedType):
    """
    A PRecord is a PMap with a fixed set of specified fields. Records are declared as python classes inheriting
    from PRecord. Because it is a PMap it has full support for all Mapping methods such as iteration and element
    access using subscript notation.

    More documentation and examples of PRecord usage is available at https://github.com/tobgu/pyrsistent
    """
    def __new__(cls, **kwargs):
        # Hack total! If these two special attributes exist that means we can create
        # ourselves. Otherwise we need to go through the Evolver to create the structures
        # for us.
        if '_precord_size' in kwargs and '_precord_buckets' in kwargs:
            return super(PRecord, cls).__new__(cls, kwargs['_precord_size'], kwargs['_precord_buckets'])

        initial_values = kwargs
        if cls._precord_initial_values:
            initial_values = dict(cls._precord_initial_values)
            initial_values.update(kwargs)

        e = _PRecordEvolver(cls, pmap())
        for k, v in initial_values.items():
            e[k] = v

        return e.persistent()

    def set(self, *args, **kwargs):
        """
        Set a field in the record. This set function differs slightly from that in the PMap
        class. First of all it accepts key-value pairs. Second it accepts multiple key-value
        pairs to perform one, atomic, update of multiple fields.
        """

        # The PRecord set() can accept kwargs since all fields that have been declared are
        # valid python identifiers. Also allow multiple fields to be set in one operation.
        if args:
            return super(PRecord, self).set(args[0], args[1])

        return self.update(kwargs)

    def evolver(self):
        """
        Returns an evolver of this object.
        """
        return _PRecordEvolver(self.__class__, self)

    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__,
                                 ', '.join('{0}={1}'.format(k, repr(v)) for k, v in self.items()))

    @classmethod
    def create(cls, kwargs):
        """
        Factory method. Will create a new PRecord of the current type and assign the values
        specified in kwargs.
        """
        if isinstance(kwargs, cls):
            return kwargs

        return cls(**kwargs)

    def __reduce__(self):
        # Pickling support
        return _restore_pickle, (self.__class__, dict(self),)

    def serialize(self, format=None):
        """
        Serialize the current PRecord using custom serializer functions for fields where
        such have been supplied.
        """
        def _serialize(k, v):
            serializer = self.__class__._precord_fields[k].serializer
            if isinstance(v, CheckedType) and serializer is _PRECORD_NO_SERIALIZER:
                return v.serialize(format)

            return serializer(format, v)

        return dict((k, _serialize(k, v)) for k, v in self.items())


class PRecordTypeError(TypeError):
    def __init__(self, source_class, field, expected_types, actual_type, *args, **kwargs):
        super(PRecordTypeError, self).__init__(*args, **kwargs)
        self.source_class = source_class
        self.field = field
        self.expected_types = expected_types
        self.actual_type = actual_type


class _PRecordEvolver(PMap._Evolver):
    __slots__ = ('_destination_cls', '_invariant_error_codes', '_missing_fields')

    def __init__(self, cls, *args):
        super(_PRecordEvolver, self).__init__(*args)
        self._destination_cls = cls
        self._invariant_error_codes = []
        self._missing_fields = []

    def __setitem__(self, key, original_value):
        self.set(key, original_value)

    def set(self, key, original_value):
        field = self._destination_cls._precord_fields.get(key)
        if field:
            try:
                value = field.factory(original_value)
            except InvariantException as e:
                self._invariant_error_codes += e.invariant_errors
                self._missing_fields += e.missing_fields
                return self

            if field.type and not any(isinstance(value, t) for t in field.type):
                actual_type = type(value)
                message = "Invalid type for field {0}.{1}, was {2}".format(self._destination_cls.__name__, key, actual_type.__name__)
                raise PRecordTypeError(self._destination_cls, key, field.type, actual_type, message)

            is_ok, error_code = field.invariant(value)
            if not is_ok:
                self._invariant_error_codes.append(error_code)

            return super(_PRecordEvolver, self).set(key, value)
        else:
            raise AttributeError("'{0}' is not among the specified fields for {1}".format(key, self._destination_cls.__name__))

    def persistent(self):
        cls = self._destination_cls
        is_dirty = self.is_dirty()
        pm = super(_PRecordEvolver, self).persistent()
        if is_dirty or not isinstance(pm, cls):
            result = cls(_precord_buckets=pm._buckets, _precord_size=pm._size)
        else:
            result = pm

        if cls._precord_mandatory_fields:
            self._missing_fields += tuple('{0}.{1}'.format(cls.__name__, f) for f
                                          in (cls._precord_mandatory_fields - set(result.keys())))

        if self._invariant_error_codes or self._missing_fields:
            raise InvariantException(tuple(self._invariant_error_codes), tuple(self._missing_fields),
                                     'Field invariant failed')

        error_codes = tuple(error_code for is_ok, error_code in
                            (invariant(result) for invariant in cls._precord_invariants) if not is_ok)
        if error_codes:
            raise InvariantException(error_codes, (), 'Global invariant failed')

        return result


############## Transform ##################

# Transformations
def inc(x):
    """ Add one to the current value """
    return x + 1

def dec(x):
    """ Subtract one from the current value """
    return x - 1

def discard(evolver, key):
    """ Discard the element and returns a structure without the discarded elements """
    try:
        del evolver[key]
    except KeyError:
        pass


# Matchers
def rex(expr):
    """ Regular expression matcher to use together with transform functions """
    r = re.compile(expr)
    return lambda key: isinstance(key, six.string_types) and r.match(key)


def ny(_):
    """ Matcher that matches any value """
    return True

# Support functions
def _chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]


def _transform(structure, transformations):
    r = structure
    for path, command in _chunks(transformations, 2):
        r = _do_to_path(r, path, command)
    return r


def _do_to_path(structure, path, command):
    if not path:
        return command(structure) if callable(command) else command

    kvs = _get_keys_and_values(structure, path[0])
    return _update_structure(structure, kvs, path[1:], command)


def _items(structure):
    try:
        return structure.items()
    except AttributeError:
        return list(enumerate(structure))


def _get(structure, key, default):
    try:
        return structure[key]
    except (IndexError, KeyError):
        return default


def _get_keys_and_values(structure, key_spec):
    if callable(key_spec):
        return [(k, v) for k, v in _items(structure) if key_spec(k)]

    return [(key_spec, _get(structure, key_spec, pmap()))]


def _update_structure(structure, kvs, path, command):
    e = structure.evolver()
    for k, v in kvs:
        if not path and command is discard:
            discard(e, k)
        else:
            result = _do_to_path(v, path, command)
            if result is not v:
                e[k] = result
    return e.persistent()


####################### Checked pvector #########################

def _store_types(dct, bases, destination_name, source_name):
    def to_list(elem):
        if not isinstance(elem, Iterable):
            return [elem]
        return list(elem)

    dct[destination_name] = to_list(dct[source_name]) if source_name in dct else []
    dct[destination_name] += sum([to_list(b.__dict__[source_name]) for b in bases if source_name in b.__dict__], [])
    dct[destination_name] = tuple(dct[destination_name])
    if not all(isinstance(t, type) for t in dct[destination_name]):
        raise TypeError('Type specifications must be types')


def _store_invariants(dct, bases, destination_name, source_name):
        # Invariants are inherited
        dct[destination_name] = [dct[source_name]] if source_name in dct else []
        dct[destination_name] += [b.__dict__[source_name] for b in bases if source_name in b.__dict__]
        dct[destination_name] = tuple(dct[destination_name])
        if not all(callable(invariant) for invariant in dct[destination_name]):
            raise TypeError('Invariants must be callable')


class _CheckedTypeMeta(type):
    def __new__(mcs, name, bases, dct):
        _store_types(dct, bases, '_checked_types', '__type__')
        _store_invariants(dct, bases, '_checked_invariants', '__invariant__')

        def default_serializer(self, _, value):
            if isinstance(value, CheckedType):
                return value.serialize()
            return value

        dct.setdefault('__serializer__', default_serializer)

        dct['__slots__'] = ()

        return super(_CheckedTypeMeta, mcs).__new__(mcs, name, bases, dct)


class CheckedTypeError(TypeError):
    def __init__(self, expected_types, actual_type, actual_value, source_class, *args, **kwargs):
        super(CheckedTypeError, self).__init__(*args, **kwargs)
        self.expected_types = expected_types
        self.actual_type = actual_type
        self.actual_value = actual_value
        self.source_class = source_class


class CheckedKeyTypeError(CheckedTypeError):
    pass


class CheckedValueTypeError(CheckedTypeError):
    pass


def _check_types(it, expected_types, source_class, exception_type=CheckedValueTypeError):
    if expected_types:
        for e in it:
            if not any(isinstance(e, t) for t in expected_types):
                actual_type = type(e)
                msg = "Type {source_class} can only be used with {expected_types}, not {actual_type}".format(
                    source_class=source_class.__name__,
                    expected_types=tuple(et.__name__ for et in expected_types),
                    actual_type=actual_type.__name__)
                raise exception_type(expected_types, actual_type, e, source_class, msg)


def _invariant_errors(elem, invariants):
    return [data for valid, data in (invariant(elem) for invariant in invariants) if not valid]


def _invariant_errors_iterable(it, invariants):
    return sum([_invariant_errors(elem, invariants) for elem in it], [])


def optional(*typs):
    """ Convenience function to specify that a value may be of any of the types in type 'typs' or None """
    return tuple(typs) + (type(None),)


def _checked_type_create(cls, source_data):
        if isinstance(source_data, cls):
            return source_data

        # Recursively apply create methods of checked types if the types of the supplied data
        # does not match any of the valid types.
        types = cls._checked_types
        checked_type = next((t for t in types if issubclass(t, CheckedType)), None)
        if checked_type:
            return cls([checked_type.create(data)
                        if not any(isinstance(data, t) for t in types) else data
                        for data in source_data])

        return cls(source_data)

@six.add_metaclass(_CheckedTypeMeta)
class CheckedPVector(_PVectorImpl, CheckedType):
    """
    A CheckedPVector is a PVector which allows specifying type and invariant checks.

    >>> class Positives(CheckedPVector):
    ...     __type__ = (long, int)
    ...     __invariant__ = lambda n: (n >= 0, 'Negative')
    ...
    >>> Positives([1, 2, 3])
    Positives([1, 2, 3])
    """

    __slots__ = ()

    def __new__(cls, initial=()):
        if type(initial) == _PVectorImpl:
            return super(CheckedPVector, cls).__new__(cls, initial._count, initial._shift, initial._root, initial._tail)

        return CheckedPVector.Evolver(cls, _pvector()).extend(initial).persistent()

    def set(self, key, value):
        return self.evolver().set(key, value).persistent()

    def append(self, val):
        return self.evolver().append(val).persistent()

    def extend(self, it):
        return self.evolver().extend(it).persistent()

    create = classmethod(_checked_type_create)

    def serialize(self, format=None):
        serializer = self.__serializer__
        return list(serializer(format, v) for v in self)

    def __reduce__(self):
        # Pickling support
        return _restore_pickle, (self.__class__, list(self),)

    class Evolver(_PVectorImpl.Evolver):
        __slots__ = ('_destination_class', '_invariant_errors')

        def __init__(self, destination_class, vector):
            super(CheckedPVector.Evolver, self).__init__(vector)
            self._destination_class = destination_class
            self._invariant_errors = []

        def _check(self, it):
            _check_types(it, self._destination_class._checked_types, self._destination_class)
            error_data = _invariant_errors_iterable(it, self._destination_class._checked_invariants)
            self._invariant_errors.extend(error_data)

        def __setitem__(self, key, value):
            self._check([value])
            return super(CheckedPVector.Evolver, self).__setitem__(key, value)

        def append(self, elem):
            self._check([elem])
            return super(CheckedPVector.Evolver, self).append(elem)

        def extend(self, it):
            self._check(it)
            return super(CheckedPVector.Evolver, self).extend(it)

        def persistent(self):
            if self._invariant_errors:
                raise InvariantException(error_codes=self._invariant_errors)

            result = self._orig_pvector
            if self.is_dirty() or (self._destination_class != type(self._orig_pvector)):
                pv = super(CheckedPVector.Evolver, self).persistent().extend(self._extra_tail)
                result = self._destination_class(pv)
                self._reset(result)

            return result

    def __repr__(self):
        return self.__class__.__name__ + "({0})".format(self.tolist())

    __str__ = __repr__

    def evolver(self):
        return CheckedPVector.Evolver(self.__class__, self)


@six.add_metaclass(_CheckedTypeMeta)
class CheckedPSet(PSet, CheckedType):
    """
    A CheckedPVector is a PSet which allows specifying type and invariant checks.

    >>> class Positives(CheckedPSet):
    ...     __type__ = (long, int)
    ...     __invariant__ = lambda n: (n >= 0, 'Negative')
    ...
    >>> Positives([1, 2, 3])
    Positives([1, 2, 3])
    """

    __slots__ = ()

    def __new__(cls, initial=()):
        if type(initial) is PMap:
            return super(CheckedPSet, cls).__new__(cls, initial)

        evolver = CheckedPSet.Evolver(cls, pset())
        for e in initial:
            evolver.add(e)

        return evolver.persistent()

    def __repr__(self):
        return self.__class__.__name__ + super(CheckedPSet, self).__repr__()[4:]

    def __str__(self):
        return self.__repr__()

    def serialize(self, format=None):
        serializer = self.__serializer__
        return set(serializer(format, v) for v in self)

    create = classmethod(_checked_type_create)

    def __reduce__(self):
        # Pickling support
        return _restore_pickle, (self.__class__, list(self),)

    def evolver(self):
        return CheckedPSet.Evolver(self.__class__, self)

    class Evolver(PSet._Evolver):
        __slots__ = ('_destination_class', '_invariant_errors')

        def __init__(self, destination_class, original_set):
            super(CheckedPSet.Evolver, self).__init__(original_set)
            self._destination_class = destination_class
            self._invariant_errors = []

        def _check(self, it):
            _check_types(it, self._destination_class._checked_types, self._destination_class)
            error_data = _invariant_errors_iterable(it, self._destination_class._checked_invariants)
            self._invariant_errors.extend(error_data)

        def add(self, element):
            self._check([element])
            self._pmap_evolver[element] = True
            return self

        def persistent(self):
            if self._invariant_errors:
                raise InvariantException(error_codes=self._invariant_errors)

            if self.is_dirty() or self._destination_class != type(self._original_pset):
                return self._destination_class(self._pmap_evolver.persistent())

            return self._original_pset


class _CheckedMapTypeMeta(type):
    def __new__(mcs, name, bases, dct):
        _store_types(dct, bases, '_checked_key_types', '__key_type__')
        _store_types(dct, bases, '_checked_value_types', '__value_type__')
        _store_invariants(dct, bases, '_checked_invariants', '__invariant__')

        def default_serializer(self, _, key, value):
            sk = key
            if isinstance(key, CheckedType):
                sk = key.serialize()

            sv = value
            if isinstance(value, CheckedType):
                sv = value.serialize()

            return sk, sv

        dct.setdefault('__serializer__', default_serializer)

        dct['__slots__'] = ()

        return super(_CheckedMapTypeMeta, mcs).__new__(mcs, name, bases, dct)

# Marker object
_UNDEFINED_CHECKED_PMAP_SIZE = object()


@six.add_metaclass(_CheckedMapTypeMeta)
class CheckedPMap(PMap, CheckedType):
    """
    A CheckedPMap is a PMap which allows specifying type and invariant checks.

    >>> class IntToFloatMap(CheckedPMap):
    ...     __key_type__ = int
    ...     __value_type__ = float
    ...     __invariant__ = lambda k, v: (int(v) == k, 'Invalid mapping')
    ...
    >>> IntToFloatMap({1: 1.5, 2: 2.25})
    IntToFloatMap({1: 1.5, 2: 2.25})
    """

    __slots__ = ()

    def __new__(cls, initial={}, size=_UNDEFINED_CHECKED_PMAP_SIZE):
        if size is not _UNDEFINED_CHECKED_PMAP_SIZE:
            return super(CheckedPMap, cls).__new__(cls, size, initial)

        evolver = CheckedPMap.Evolver(cls, pmap())
        for k, v in initial.items():
            evolver.set(k, v)

        return evolver.persistent()

    def evolver(self):
        return CheckedPMap.Evolver(self.__class__, self)

    def __repr__(self):
        return self.__class__.__name__ + "({0})".format(str(dict(self)))

    __str__ = __repr__

    def serialize(self, format=None):
        serializer = self.__serializer__
        return dict(serializer(format, k, v) for k, v in self.items())

    @classmethod
    def create(cls, source_data):
        if isinstance(source_data, cls):
            return source_data

        # Recursively apply create methods of checked types if the types of the supplied data
        # does not match any of the valid types.
        key_types = cls._checked_key_types
        checked_key_type = next((t for t in key_types if issubclass(t, CheckedType)), None)
        value_types = cls._checked_value_types
        checked_value_type = next((t for t in value_types if issubclass(t, CheckedType)), None)

        if checked_key_type or checked_value_type:
            return cls(dict((checked_key_type.create(key) if checked_key_type and not any(isinstance(key, t) for t in key_types) else key,
                             checked_value_type.create(value) if checked_value_type and not any(isinstance(value, t) for t in value_types) else value)
                            for key, value in source_data.items()))

        return cls(source_data)

    def __reduce__(self):
        # Pickling support
        return _restore_pickle, (self.__class__, dict(self),)

    class Evolver(PMap._Evolver):
        __slots__ = ('_destination_class', '_invariant_errors')

        def __init__(self, destination_class, original_map):
            super(CheckedPMap.Evolver, self).__init__(original_map)
            self._destination_class = destination_class
            self._invariant_errors = []

        def set(self, key, value):
            _check_types([key], self._destination_class._checked_key_types, self._destination_class, CheckedKeyTypeError)
            _check_types([value], self._destination_class._checked_value_types, self._destination_class)
            self._invariant_errors.extend(data for valid, data in (invariant(key, value)
                                                                   for invariant in self._destination_class._checked_invariants)
                                          if not valid)

            return super(CheckedPMap.Evolver, self).set(key, value)

        def persistent(self):
            if self._invariant_errors:
                raise InvariantException(error_codes=self._invariant_errors)

            if self.is_dirty() or type(self._original_pmap) != self._destination_class:
                return self._destination_class(self._buckets_evolver.persistent(), self._size)

            return self._original_pmap