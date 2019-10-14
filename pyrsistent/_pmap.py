from ._compat import Mapping, Hashable
import six
from pyrsistent._transformations import transform
from immutables import Map as _IMap


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

    PMap implements the Mapping protocol and is Hashable. It also supports dot-notation for
    element access.

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
    >>> m3.c
    3
    """
    __slots__ = ('_imap', '__weakref__')

    # TODO: Fix PRecord
    def __new__(cls, _imap):
        self = super(PMap, cls).__new__(cls)
        self._imap = _imap
        return self

    def __getitem__(self, key):
        return self._imap[key]

    def __contains__(self, key):
        return key in self._imap

    def get(self, key, default=None):
        return self._imap.get(key, default)

    def __iter__(self):
        return iter(self._imap)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                "{0} has no attribute '{1}'".format(type(self).__name__, key)
            )

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
        return self._imap.items()

    def values(self):
        return self._imap.values()

    def keys(self):
        return self._imap.keys()

    def items(self):
        return self._imap.items()

    def __len__(self):
        return len(self._imap)

    def __repr__(self):
        return 'pmap({0})'.format(str(dict(self)))

    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, Mapping):
            return NotImplemented
        if len(self) != len(other):
            return False
        if isinstance(other, PMap):
            if (hasattr(self, '_cached_hash') and hasattr(other, '_cached_hash')
                    and self._cached_hash != other._cached_hash):
                return False
            return self._imap == other._imap
        elif isinstance(other, dict):
            return dict(self.iteritems()) == other
        return dict(self.iteritems()) == dict(six.iteritems(other))

    __ne__ = Mapping.__ne__

    def __lt__(self, other):
        raise TypeError('PMaps are not orderable')

    __le__ = __lt__
    __gt__ = __lt__
    __ge__ = __lt__

    def __str__(self):
        return self.__repr__()

    def __hash__(self):
        return hash(self._imap)

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
        return PMap(self._imap.set(key, val))

    def remove(self, key):
        """
        Return a new PMap without the element specified by key. Raises KeyError if the element
        is not present.

        >>> m1 = m(a=1, b=2)
        >>> m1.remove('a')
        pmap({'b': 2})
        """
        return PMap(self._imap.delete(key))

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

    def __add__(self, other):
        return self.update(other)

    def __reduce__(self):
        # Pickling support
        return pmap, (dict(self),)

    def transform(self, *transformations):
        """
        Transform arbitrarily complex combinations of PVectors and PMaps. A transformation
        consists of two parts. One match expression that specifies which elements to transform
        and one transformation function that performs the actual transformation.

        >>> from pyrsistent import freeze, ny
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
        return transform(self, transformations)

    def copy(self):
        return self

    class _Evolver(object):
        __slots__ = ('_original_pmap', '_mutation', '_is_dirty')

        def __init__(self, original_pmap):
            self._original_pmap = original_pmap
            self._mutation = original_pmap._imap.mutate()
            self._is_dirty = False

        def __getitem__(self, key):
            return self._mutation[key]

        def __setitem__(self, key, val):
            self._is_dirty = True
            self._mutation.set(key, val)

        def set(self, key, val):
            self[key] = val

        def is_dirty(self):
            return self._is_dirty

        def persistent(self):
            if self._is_dirty:
                self._original_pmap = PMap(self._mutation.finish())

            return self._original_pmap

        def __len__(self):
            return self._size

        def __contains__(self, key):
            return key in self._mutation

        def __delitem__(self, key):
            self._is_dirty = True
            self.remove(key)

        def remove(self, key):
            del self[key]

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
        persistent() function on the evolver.

        >>> m2 = e.persistent()
        >>> m2
        pmap({'c': 3, 'b': 2})

        The new pmap will share data with the original pmap in the same way that would have
        been done if only using operations on the pmap.
        """
        return self._Evolver(self)

Mapping.register(PMap)
Hashable.register(PMap)

_EMPTY_IMAP = _IMap()
_EMPTY_PMAP = PMap(_EMPTY_IMAP)


def pmap(initial={}, pre_size=0):
    # TODO: Pre-size not needed anymore?
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

    m = _EMPTY_IMAP.mutate()
    m.update(six.iteritems(initial))
    return PMap(m.finish())


def m(**kwargs):
    """
    Creates a new persitent map. Inserts all key value arguments into the newly created map.

    >>> m(a=13, b=14)
    pmap({'a': 13, 'b': 14})
    """
    return pmap(kwargs)
