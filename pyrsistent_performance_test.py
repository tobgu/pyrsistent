from pyrsistent import pvector

#import pytest
import time

def test_big_iterator_initialization():
    """
    The results are comparable to those of doing it with a list since most of the
    code is shared.
    """
    before = time.time()
    iterator = (x for x in range(1000000))
    print "Big iterator: " + str(time.time() - before)

    before = time.time()
    seq = pvector(iterator)
    print "Big vector from iterator: " + str(time.time() - before)


def test_big_list_initialization():
    """
    Some example results, these are some of the fastest I've seen, it tends to vary...

    == CPython ==
    Big list: 0.174705028534
    Big vector: 0.353514909744

    == PyPy ==
    Slicing solution PyPy:
    Big list: 0.0481958389282
    Big vector from list: 0.166031122208

    """
    before = time.time()
    list = [x for x in range(1000000)]
    print "Big list: " + str(time.time() - before)

    before = time.time()
    seq = pvector(list)
    print "Big vector from list: " + str(time.time() - before)


def test_slicing_performance():
    """
    Again, the fastest, large variations exist...

    == CPython ==
    List slicing: 0.00921297073364
    Pvec slicing: 0.225503921509

    == PyPy ==
    List slicing: 0.00399494171143
    Pvec slicing: 0.102802991867

    """

    list = [x for x in range(1000000)]

    before = time.time()
    sublist = list[533:744444]
    print "List slicing: " + str(time.time() - before)

    vec = pvector(list)
    before = time.time()
    subvec = vec[533:744444]
    print "Pvec slicing: " + str(time.time() - before)


def test_create_many_small_vectors():
    """
    == PyPy ==
    Single element: 0.149819135666
    Double elements: 0.350324869156
    Ten elements: 0.338271856308

    === CPython ===
    Single element: 3.62240195274
    Double elements: 8.04715490341
    Ten elements: 5.73595809937
    """
    iterations = range(1000000)

    before = time.time()
    single = [2]
    for _ in iterations:
        vec = pvector(single)
    print "Single element: " + str(time.time() - before)


    before = time.time()
    double = [2, 3]
    for _ in iterations:
        vec = pvector(double)
    print "Double elements: " + str(time.time() - before)

    before = time.time()
    ten = range(10)
    for _ in iterations:
        vec = pvector(ten)
    print "Ten elements: " + str(time.time() - before)


if __name__ == "__main__":
    test_big_list_initialization()
    test_big_iterator_initialization()
    test_slicing_performance()
    test_create_many_small_vectors()