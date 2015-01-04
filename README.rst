Pyrsistent introduction
=======================

Pyrsistent is a number of persistent collections (by some referred to as functional data structures). Persistent in 
the sense that they are immutable.

All methods on a data structure that would normally mutate it instead return a new copy of the structure containing the
requested updates. The original structure is left untouched.

This will simplify the reasoning about what a program does since no hidden side effects ever can take place to these
data structures. You can rest assured that the object you hold a reference to will remain the same throughout its
lifetime and need not worry that somewhere five stack levels below you in the darkest corner of your application
someone has decided to remove that element that you expected to be there.

Pyrsistent is influenced by persistent data structures such as those found in the standard library of Clojure. The
data structures are designed to share common elements through path copying.
It aims at taking these concepts and make them as pythonic as possible so that they can be easily integrated into any python
program without hassle.

Examples
--------
.. _Sequence: collections_
.. _Hashable: collections_
.. _Mapping: collections_
.. _Mappings: collections_
.. _Set: collections_
.. _collections: https://docs.python.org/3/library/collections.abc.html
.. _documentation: http://pyrsistent.readthedocs.org/

The collection types currently implemented are PVector (similar to a python list), PMap (similar to
dict), PSet (similar to set), PBag (similar to collections.Counter), PList (a classic
singly linked list) and PDeque (similar to collections.deque). There is also an immutable object type (pclass)
built on the named tuple as well as freeze and thaw functions to convert between pythons standard collections
and pyrsistent collections.

Below are examples of common usage patterns for some of the structures. More information and
full documentation for all data structures is available in the documentation_.

PVector
~~~~~~~
With full support for the Sequence_ protocol PVector is meant as a drop in replacement to the built in list from a readers
point of view. Write operations of course differ since no in place mutation is done but naming should be in line
with corresponding operations on the built in list.

Support for the Hashable_ protocol also means that it can be used as key in Mappings_.

Appends are amortized O(1). Random access and insert is log32(n) where n is the size of the vector.

.. code:: python

    >>> from pyrsistent import v, pvector

    # No mutation of vectors once created, instead they
    # are "evolved" leaving the original untouched
    >>> v1 = v(1, 2, 3)
    >>> v2 = v1.append(4)
    >>> v3 = v2.set(1, 5)
    >>> v1
    pvector([1, 2, 3])
    >>> v2
    pvector([1, 2, 3, 4])
    >>> v3
    pvector([1, 5, 3, 4])

    # Random access and slicing
    >>> v3[1]
    5
    >>> v3[1:3]
    pvector([5, 3])

    # Iteration
    >>> list(x + 1 for x in v3)
    [2, 6, 4, 5]
    >>> pvector(2 * x for x in range(3))
    pvector([0, 2, 4])

PMap
~~~~
With full support for the Mapping_ protocol PMap is meant as a drop in replacement to the built in dict from a readers point
of view. Support for the Hashable_ protocol also means that it can be used as key in other Mappings_.

Random access and insert is log32(n) where n is the size of the map.

.. code:: python

    >>> from pyrsistent import m, pmap, v

    # No mutation of maps once created, instead they are
    # "evolved" leaving the original untouched
    >>> m1 = m(a=1, b=2)
    >>> m2 = m1.set('c', 3)
    >>> m3 = m2.set('a', 5)
    >>> m1
    pmap({'a': 1, 'b': 2})
    >>> m2
    pmap({'a': 1, 'c': 3, 'b': 2})
    >>> m3
    pmap({'a': 5, 'c': 3, 'b': 2})
    >>> m3['a']
    5

    # Evolution of nested persistent structures
    >>> m4 = m(a=5, b=6, c=v(1, 2))
    >>> m4.set_in(('c', 1), 17)
    pmap({'a': 5, 'c': pvector([1, 17]), 'b': 6})
    >>> m5 = m(a=1, b=2)

    # Evolve by merging with other mappings
    >>> m5.update(m(a=2, c=3), {'a': 17, 'd': 35})
    pmap({'a': 17, 'c': 3, 'b': 2, 'd': 35})

    # Dict-like methods to convert to list and iterate
    >>> m3.items()
    [('a', 5), ('c', 3), ('b', 2)]
    >>> list(m3)
    ['a', 'c', 'b']

PSet
~~~~
With full support for the Set_ protocol PSet is meant as a drop in replacement to the built in set from a readers point
of view. Support for the Hashable_ protocol also means that it can be used as key in Mappings_.

Random access and insert is log32(n) where n is the size of the set.

.. code:: python

    >>> from pyrsistent import s

    # No mutation of sets once created, you know the story...
    >>> s1 = s(1, 2, 3, 2)
    >>> s2 = s1.add(4)
    >>> s3 = s1.remove(1)
    >>> s1
    pset([1, 2, 3])
    >>> s2
    pset([1, 2, 3, 4])
    >>> s3
    pset([2, 3])

    # Full support for set operations
    >>> s1 | s(3, 4, 5)
    pset([1, 2, 3, 4, 5])
    >>> s1 & s(3, 4, 5)
    pset([3])
    >>> s1 < s2
    True
    >>> s1 < s(3, 4, 5)
    False

Evolvers
~~~~~~~~
PVector, PMap and PSet all have support for a concept dubbed *evolvers*. An evolver acts like a mutable
view of the underlying persistent data structure with "transaction like" semantics. No updates of the original
data structure is ever performed, it is still fully immutable.

The evolvers have a very limited API by design to discourage excessive, and inappropriate, usage as that would
take us down the mutable road. In principle only basic mutation and element access functions are supported.
Check out the documentation_ of each data structure for specific examples.

Examples of when you may want to use an evolver instead of working directly with the data structure include:

* Multiple updates are done to the same data structure and the intermediate results are of no
  interest. In this case using an evolver may be a more efficient and easier to work with.
* You need to pass a vector into a legacy function or a function that you have no control
  over which performs in place mutations. In this case pass an evolver instance
  instead and then create a new pvector from the evolver once the function returns.

.. code:: python

    >>> from pyrsistent import v

    # In place mutation as when working with the built in counterpart
    >>> v1 = v(1, 2, 3)
    >>> e = v1.evolver()
    >>> e[1] = 22
    >>> e.append(4)
    >>> e.extend([5, 6])
    >>> e[5] += 1
    >>> len(e)
    6

    # The evolver is considered *dirty* when it contains changes compared to the underlying vector
    >>> e.is_dirty()
    True

    # But the underlying pvector still remains untouched
    >>> v1
    pvector([1, 2, 3])

    # Once satisfied with the updates you can produce a new pvector containing the updates.
    # The new pvector will share data with the original pvector in the same way that would have
    # been done if only using operations on the pvector.
    >>> v2 = e.pvector()
    >>> v2
    pvector([1, 22, 3, 4, 5, 7])

    # The evolver is now no longer considered *dirty* as it contains no differences compared to the
    # pvector just produced.
    >>> e.is_dirty()
    False

    # You may continue to work with the same evolver without affecting the content of v2
    >>> e[0] = 11

    # Or create a new evolver from v2. The two evolvers can be updated independently but will both
    # share data with v2 where possible.
    >>> e2 = v2.evolver()
    >>> e2[0] = 1111
    >>> e.pvector()
    pvector([11, 22, 3, 4, 5, 7])
    >>> e2.pvector()
    pvector([1111, 22, 3, 4, 5, 7])

freeze and thaw
~~~~~~~~~~~~~~~
These functions are great when your cozy immutable world has to interact with the evil mutable world outside.

.. code:: python

    >>> from pyrsistent import freeze, thaw, v, m
    >>> freeze([1, {'a': 3}])
    pvector([1, pmap({'a': 3})])
    >>> thaw(v(1, m(a=3)))
    [1, {'a': 3}]

Compatibility
-------------

Pyrsistent is developed and tested on Python 2.6, 2.7, 3.2, 3.4 and PyPy (Python 2.7 compatible). It will most likely work
on all other versions >= 3.2 but no guarantees are given. :)

Performance
-----------

Pyrsistent is developed with performance in mind. Still, while some operations are nearly on par with their built in, 
mutable, counterparts in terms of speed, other operations are slower. In the cases where attempts at
optimizations have been done, speed has generally been valued over space.

Pyrsistent comes with two API compatible flavors of PVector (on which PMap and PSet are based), one pure Python 
implementation and one implemented as a C extension. The latter generally being 2 - 20 times faster than the former.
The C extension will be used automatically when possible.

The pure python implementation is fully PyPy compatible. Running it under PyPy speeds operations up considerably if 
the structures are used heavily (if JITed), for some cases the performance is almost on par with the built in counterparts.

Installation
------------

pip install pyrsistent

Documentation
-------------

Available at http://pyrsistent.readthedocs.org/

Brief presentation available at http://slides.com/tobiasgustafsson/immutability-and-python/

Contributors
------------

Tobias Gustafsson https://github.com/tobgu

Christopher Armstrong https://github.com/radix

Contributing
------------

If you experience problems please log them on GitHub. If you want to contribute code, please fork the code and submit a pull request.
