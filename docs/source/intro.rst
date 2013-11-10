Pyrsistent introduction
=======================
Pyrsistent is a number of persistent collections. Persistent in the sense that they are immutable (if only accessing
the public API). The collection types currently implemented are PVector (similar to a python list), PMap (similar to
a python dict) and PSet (similar to a python set).

All methods on a data structure that manipulates it returns a new copy of the object with the containing the
requested updates rather than manipulating the original.

This will simplify the reasoning about what a program does since no hidden side effects ever can take place to these
data structures. You can rest assured that the object you hold a reference to will remain the same throughout its
lifetime and need not worry that somewhere five stack levels below you in the darkest corner of your application
someone has decided to remove that element that you expected to be there.

The following code snippet illustrated the difference between the built in, regular, list and the pvector which
is part of this library


>>> from pyrsistent import pvec
>>> l = [1, 2, 3]
>>> l. append(4)
>>> print l
[1, 2, 3, 4]
>>> p1 = pvec(1, 2, 3)
>>> p2 = p1.append(4)
>>> print p1
[1, 2, 3]
>>> print p2
[1, 2, 3, 4]

Performance is generally in the range of 2 - 100 times slower than using the corresponding built in types in Python.
In the cases where attempts at optimizations have been done, speed has generally been valued over space.

Pyrsistent is fully PyPy compatible, running it under PyPy speeds operations up considerably if the structures are used
heavily (if JITed), for some cases the performance is almost on par with the built in counterparts.

It has been developed on Python 2.7 and is not yet tested on Python 3.x.