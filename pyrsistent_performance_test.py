from pyrsistent import pvector, pset

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


def test_set_performance():
    """
    == PyPy ==
    Big set from list: 0.0152490139008
    Big pset from list: 1.62447595596
    Random access set: 0.0192308425903
    Random access pset: 2.18643188477

    === CPython ===
    Big set from list: 0.0202131271362
    Big pset from list: 2.87654399872
    Random access set: 0.0950989723206
    Random access pset: 11.2261350155
    """
    l = [x for x in range(100000)]

    before = time.time()
    s1 = set(l)
    print "Big set from list: " + str(time.time() - before)

    before = time.time()
    s2 = pset(l)
    print "Big pset from list: " + str(time.time() - before)

    before = time.time()
    random_access(s1)
    print "Random access set: " + str(time.time() - before)

    before = time.time()
    random_access(s2)
    print "Random access pset: " + str(time.time() - before)

def random_access(s):
    testdata = [0, 4, 55, 10000, 98763, -2, 30000, 42004, 37289, 100, 2, 999999]
    result = False
    for x in range(100000):
        for y in testdata:
            result = y in s

    return result

if __name__ == "__main__":
#    test_big_list_initialization()
#    test_big_iterator_initialization()
#    test_slicing_performance()
#    test_create_many_small_vectors()
    test_set_performance()
