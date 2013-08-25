# from pyrsistent import pvector 
from collections import Sequence
from pyrsistentc import pvec

import unittest

class TestPyVec(unittest.TestCase):

    def test_appends_to_small_and_medium_sized_vectors(self):
        # Tests inserts where either the insert fits in the tail, or
        # it fits in the first level of the root node.
        p_next = pvec()
        count = 0
        c = 0
        for x in range(99):
            p_next = p_next.append(x)
            count += 1
            c+=1
            for y in range(x+1):
                count += 1
                self.assertEqual(p_next[y], y)

    def test_random_insert_in_vector(self):
        x = pvec(range(2000))
        for i in x:
            y = x.assoc(i, x[i] * 10000)
            self.assertEqual(y[i], x[i] * 10000)

    def test_random_insert_end_of_vector(self):
        x = pvec(range(20))
        y = x.assoc(20, 200)
        self.assertEqual(y[20], 200)

    def test_random_insert_out_of_bounds(self):
        print "Hej"
        x = pvec()
        self.assertRaises(IndexError, x.assoc, 21, 200)

    def test_construction_with_argument(self):
        x = pvec(range(2000))
        for i in x:
            self.assertEqual(i, x[i])


    def xtest_infinity(self):
        print "Starting to test infinity"

#        while True:
        x = pvec()
        print("Start")
        for z in range(10000000):
            x = x.append(z)
        print("Stop")


    def test_appends_to_large_sized_vectors(self):
        # Tests appends where the inserts do not fit within the first level
        # of the root but must be pushed further down the tree.
        p_next = pvec()
        size = 32 * 32 * 32 + 32
        for x in range(size):
            p_next = p_next.append(x)
            self.assertEqual(p_next[x], x)

        for x in range(size):
            self.assertEqual(p_next[x], x)

    def test_pvec_is_a_collection(self):
        # Check that inheritance works as expected
        assert isinstance(pvec(), Sequence)

    # TODO Investigate why there are segmentation faults when these functions are removed
    def xtest_2_random_insert_out_of_bounds(self):
        print "Hej igen"

if __name__ == '__main__':
#    import cProfile
#    cProfile.run('insert_in_vector()')
    unittest.main()
