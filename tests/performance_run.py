from itertools import repeat
from pyrsistent import pvector, pset

import time

def run_big_iterator_initialization():
    """
    The results are comparable to those of doing it with a list since most of the
    code is shared.
    """
    before = time.time()
    iterator = (x for x in range(1000000))
    print("Big iterator: " + str(time.time() - before))

    before = time.time()
    seq = pvector(iterator)
    print("Big vector from iterator: " + str(time.time() - before))


def run_big_list_initialization():
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
    l = [x for x in range(1000000)]
    print("Big list from list comprehension: " + str(time.time() - before))

    before = time.time()
    seq = pvector(l)
    print("Big vector from list: " + str(time.time() - before))


def run_slicing_performance():
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
    print("List slicing: " + str(time.time() - before))

    vec = pvector(list)
    before = time.time()
    subvec = vec[533:744444]
    print("Pvec slicing: " + str(time.time() - before))


def run_create_many_small_vectors():
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
    iterations = range(100000)

    before = time.time()
    single = [2]
    for _ in iterations:
        vec = pvector(single)
    print("Many small Single element: " + str(time.time() - before))


    before = time.time()
    double = [2, 3]
    for _ in iterations:
        vec = pvector(double)
    print("Many small Double elements: " + str(time.time() - before))

    before = time.time()
    ten = range(10)
    for _ in iterations:
        vec = pvector(ten)
    print("Many small Ten elements: " + str(time.time() - before))

    before = time.time()
    x = range(32)
    for _ in iterations:
        vec = pvector(x)
    print("Many small 32 elements: " + str(time.time() - before))

    before = time.time()
    x = range(33)
    for _ in iterations:
        vec = pvector(x)
    print("Many small 33 elements: " + str(time.time() - before))

def run_set_performance():
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
    print("Big set from list: " + str(time.time() - before))

    before = time.time()
    s2 = pset(l, pre_size=2*len(l))
    print("Big pset from list: " + str(time.time() - before))

    before = time.time()
    random_access(s1)
    print("Random access set: " + str(time.time() - before))

    before = time.time()
    random_access(s2)
    print("Random access pset: " + str(time.time() - before))

def run_vector_random_access_performance():
    def random_access(o):
        result = 0
        for x in range(10000):
            for y in testdata:
                result = o[y]

        return result

    testdata = [0, 4, 55, 10000, 98763, -2, 30000, 42004, 37289, 100, 2, 999999]
    l = range(1000000)
    
    before = time.time()
    random_access(l)
    print("Random access large list: " + str(time.time() - before))

    v = pvector(l)
    before = time.time()
    random_access(v)
    print("Random access large vector: " + str(time.time() - before))

    testdata = [0, 4, 17, -2, 3, 7, 8, 11, 1, 13, 18, 10]
    l = range(20)
    
    before = time.time()
    random_access(l)
    print("Random access small list: " + str(time.time() - before))

    v = pvector(l)
    before = time.time()
    random_access(v)
    print("Random access small vector: " + str(time.time() - before))
    

def run_string_from_objects():
    p = pvector(range(1000000))

    before = time.time()
    s1 = str(p)
    print("Str 1: " + str(time.time() - before))

    before = time.time()
    s2 = str(p)
    print("Str 2: " + str(time.time() - before))

def run_to_list():
    p = pvector(range(1000000))

    try:
        before = time.time()
        l1 = p.tolist()
        print("Tolist: " + str(time.time() - before))
    except:
        print("Tolist not implemented")

    before = time.time()
    l2 = list(p)
    print("Iterator: " + str(time.time() - before))

    try:
        before = time.time()
        l1 = p._totuple()
        print("Totuple: " + str(time.time() - before))
    except:
        print("Totuple not implemented")

def run_len():
    # This is quite close to the python function call overhead baseline since the function
    # itself hardly does anything. That is the only reason this test is interesting.
    v = pvector()
    r = 1000000

    before = time.time()
    for _ in range(r):
        len(v)
    len_duration = time.time() - before
    print("Len: %s s, per call %s s" % (len_duration, len_duration / r))

    before = time.time()
    for _ in range(r):
        pass
    empty_duration = time.time() - before
    print("Empty loop: %s s, per call %s s" % (empty_duration, empty_duration / r))
    print("Len estimate: %s, per call: %s" % (len_duration - empty_duration, (len_duration - empty_duration) / r))

def random_access(s):
    testdata = [0, 4, 55, 10000, 98763, -2, 30000, 42004, 37289, 100, 2, 999999]
    result = False
    for x in range(10000):
        for y in testdata:
            result = y in s

    return result

def run_multiple_random_inserts():
    from pyrsistent import _pvector as _pvector

    indices = [2, 405, 56, 5067, 15063, 7045, 19999, 10022, 6000, 4023]
    for x in range(4):
        indices.extend([i+318 for i in indices])

    print("Number of accesses: %s" % len(indices))
    print("Number of elements in vector: %s" % max(indices))

    original = _pvector(range(max(indices) + 1))
    original2 = _pvector(range(max(indices) + 1))

    # Using ordinary set
    start = time.time()
    new = original
    for r in range(10000):
        for i in indices:
            new = new.set(i, 0)
    print("Done simple, time=%s s, iterations=%s" % (time.time() - start, 10000 * len(indices)))
    assert original == original2

    # Using setter view
    start = time.time()
    evolver = original.evolver()
    for r in range(10000):
        for i in indices:
            evolver[i] = 0
    new2 = evolver.persistent()
    print("Done evolver, time=%s s, iterations=%s" % (time.time() - start, 10000 * len(indices)))

    assert original == original2

    def interleave(it1, it2):
        for i in zip(it1, it2):
            for j in i:
                yield j

    # Using mset
    start = time.time()
    new3 = original
    args = list(interleave(indices, repeat(0)))
    for _ in range(10000):
        new3 = new3.mset(*args)
    print("Done mset, time=%s s, iterations=%s" % (time.time() - start, 10000 * len(args)/2))

    assert list(new) == list(new2)
    assert list(new2) == list(new3)

def run_multiple_inserts_in_pmap():
    from pyrsistent import pmap

    COUNT = 100000
    def test_range():
        prime = 317
        return range(0, prime*COUNT, prime)

    elements = {x: x for x in test_range()}

    # Using ordinary set
    start = time.time()
    m1 = pmap(elements)
    print("Done initializing, time=%s s, count=%s" % (time.time() - start, COUNT))


    start = time.time()
    m2 = pmap()
    for x in test_range():
        m2 = m2.set(x, x)
    print("Done setting, time=%s s, count=%s" % (time.time() - start, COUNT))

    assert m1 == m2

    start = time.time()
    m3 = pmap()
    e3 = m3.evolver()
    for x in test_range():
        e3[x] = x
    m3 = e3.persistent()
    print("Done evolving, time=%s s, count=%s" % (time.time() - start, COUNT))

    assert m3 == m2

    start = time.time()
    m4 = pmap()
    m4 = m4.update(elements)
    m4 = m4.update(elements)
    print("Done updating, time=%s s, count=%s" % (time.time() - start, COUNT))

    assert m4 == m3

    start = time.time()
    m5 = pmap()
    m5 = m5.update_with(lambda l, r: r, elements)
    m5 = m5.update_with(lambda l, r: r, elements)
    print("Done updating with, time=%s s, count=%s" % (time.time() - start, COUNT))

    assert m5 == m4


if __name__ == "__main__":
    pass
#    run_multiple_inserts_in_pmap()
#    run_multiple_random_inserts()
#    run_big_list_initialization()
#    run_big_iterator_initialization()
#    run_slicing_performance()
#    run_create_many_small_vectors()
#    run_set_performance()
#    run_string_from_objects()
#    run_to_list()
#    run_len()
#    run_vector_random_access_performance()
