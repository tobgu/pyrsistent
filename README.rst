Pyrsistent introduction
=======================
Pyrsistent is a number of persistent collections. Persistent in the sense that they are immutable (if only accessing
the public API). The collection types currently implemented are PVector (similar to a python list), PMap (similar to
a python dict) and PSet (similar to a python set).

All methods on a data structure that would normally mutate it instead returns a new copy of the structure containing the
requested updates. The original structure is left untouched.

This will simplify the reasoning about what a program does since no hidden side effects ever can take place to these
data structures. You can rest assured that the object you hold a reference to will remain the same throughout its
lifetime and need not worry that somewhere five stack levels below you in the darkest corner of your application
someone has decided to remove that element that you expected to be there.

The following code snippet illustrated the difference between the built in, regular, list and the vector which
is part of this library


>>> from pyrsistent import v
>>> l = [1, 2, 3]
>>> l.append(4)
>>> print l
[1, 2, 3, 4]
>>> p1 = v(1, 2, 3)
>>> p2 = p1.append(4)
>>> print p1
(1, 2, 3)
>>> print p2
(1, 2, 3, 4)

Performance is generally in the range of 1 - 100 times slower than using the corresponding built in types in Python.
In the cases where attempts at optimizations have been done, speed has generally been valued over space.

Pyrsistent comes with two API compatible flavors of PVector (on which PMap and PSet are based), one pure Python 
implementation and one implemented as a C extension. The latter generally being 2 - 10 times faster than the former.
The C extension will be used automatically when possible.

The pure python implementation is fully PyPy compatible. Running it under PyPy speeds operations up considerably if 
the structures are used heavily (if JITed), for some cases the performance is almost on par with the built in counterparts.

Pyrsistent has been developed and tested on Python 2.7 and Python 3.2. It will most likely work on any later versions
of Python 3 as well but no guarantees are given. :)

Pyrsistent is influenced by persistent data structures such as those found in the standard library of Clojure. It
aims at taking these concepts and make them as pythonic as possible so that they can be easily integrated into any python
program without hassle.

Installation
-------------

pip install pyrsistent

Documentation
---------------

Available at http://pyrsistent.readthedocs.org/
