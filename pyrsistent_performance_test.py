from pyrsistent import pvector

#import pytest
import time

def test_big_iterator_initialization():
    before = time.time()
    iterator = (x for x in range(1000000))
    print "Big iterator: " + str(time.time() - before)

    before = time.time()
    seq = pvector(iterator)
    print "Big vector from iterator: " + str(time.time() - before)


def test_big_list_initialization():
    """
    Some example results
    --------------------

    == CPython ==
    Append only solution cpython:
    (pyrsistent)tobias@Astor-Ubuntu:~/Development/python/pyrsistent/pyrsistent$ python pyrsistent_performance_test.py
    Diff list: 0.177649021149
    Diff vector: 3.94124817848

    Extend solution cpython:
    (pyrsistent)tobias@Astor-Ubuntu:~/Development/python/pyrsistent/pyrsistent$ python pyrsistent_performance_test.py
    Diff list: 0.181011199951
    Diff vector: 2.28535413742

    Slicing solution cpython:
    (pyrsistent)tobias@Astor-Ubuntu:~/Development/python/pyrsistent/pyrsistent$ python pyrsistent_performance_test.py
    Diff list: 0.174705028534
    Diff vector: 0.353514909744

    == PyPy ==
    Append only solution PyPy:
    (pyrsistent)tobias@Astor-Ubuntu:~/Development/python/pyrsistent/pyrsistent$ ../../pypy/pypy-2.1/bin/pypy pyrsistent_performance_test.py
    Diff list: 0.0462861061096
    Diff vector: 0.719169139862

    Extend solution PyPy:
    (pyrsistent)tobias@Astor-Ubuntu:~/Development/python/pyrsistent/pyrsistent$ ../../pypy/pypy-2.1/bin/pypy pyrsistent_performance_test.py
    Diff list: 0.0473370552063
    Diff vector: 0.300212144852

    Slicing solution PyPy:
    (pyrsistent)tobias@Astor-Ubuntu:~/Development/python/pyrsistent/pyrsistent$ ../../pypy/pypy-2.1/bin/pypy pyrsistent_performance_test.py
    Diff list: 0.0519659519196
    Diff vector: 0.277094125748

    """
    before = time.time()
    list = [x for x in range(1000000)]
    print "Big list: " + str(time.time() - before)

    before = time.time()
    seq = pvector(list)
    print "Big vector from list: " + str(time.time() - before)


def test_slicing_performance():
    list = [x for x in range(1000000)]

    before = time.time()
    sublist = list[533:744444]
    print "List slicing: " + str(time.time() - before)

    vec = pvector(list)
    before = time.time()
    subvec = vec[533:744444]
    print "Pvec slicing: " + str(time.time() - before)


if __name__ == "__main__":
    test_big_list_initialization()
    test_big_iterator_initialization()
    test_slicing_performance()