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

The following code snippet illustrates the difference between the built in, regular, list and the vector which
is part of this library


>>> from pyrsistent import v
>>> l = [1, 2, 3]
>>> l.append(4)
>>> print l
[1, 2, 3, 4]
>>> p1 = v(1, 2, 3)
>>> p2 = p1.append(4)
>>> print p1
pvector([1, 2, 3])
>>> print p2
pvector([1, 2, 3, 4])

The collection types currently implemented are PVector (similar to a python list), PMap (similar to
a python dict), PSet (similar to a python set), PBag (similar to collections.Counter), PList (a classic
singly linked list) and PDeque (similar to collections.deque). There is also an immutable object type
built on the named tuple as well as freeze and thaw functions to convert between pythons standard collections
and pyrsistent collections.

Pyrsistent is influenced by persistent data structures such as those found in the standard library of Clojure. It
aims at taking these concepts and make them as pythonic as possible so that they can be easily integrated into any python
program without hassle.

Compatibility
-------------

Pyrsistent is developed and tested on Python 2.7, 3.2, 3.4 and PyPy (Python 2.7 compatible). It will most likely work 
on all other versions >= 3.2 but no guarantees are given. :)

Performance
-----------

Pyrsistent is developed with performance in mind. Still, while some operations are nearly on par with their built in, 
mutable, counterparts in terms of speed, other operations are considerably slower. In the cases where attempts at 
optimizations have been done, speed has generally been valued over space.

Pyrsistent comes with two API compatible flavors of PVector (on which PMap and PSet are based), one pure Python 
implementation and one implemented as a C extension. The latter generally being 2 - 20 times faster than the former.
The C extension will be used automatically when possible.

The pure python implementation is fully PyPy compatible. Running it under PyPy speeds operations up considerably if 
the structures are used heavily (if JITed), for some cases the performance is almost on par with the built in counterparts.


Installation
-------------

pip install pyrsistent

Documentation
---------------

Available at http://pyrsistent.readthedocs.org/

Brief presentation available at http://slides.com/tobiasgustafsson/immutability-and-python/

Contributors
------------

Tobias Gustafsson https://github.com/tobgu

Christopher Armstrong https://github.com/radix

Contributing
------------

If you experience problems please log them on GitHub. If you want to contribute code, please fork the code and submit a pull request.
