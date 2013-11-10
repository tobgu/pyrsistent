# from pyrsistent import pvector 
from collections import Sequence
from pyrsistentc import pvec, PVector

import unittest

class TestPyVec(unittest.TestCase):

    def test_appends_to_small_and_medium_sized_vectors(self):
        print("Start 1")
#        p = PVector()
        # Tests inserts where either the insert fits in the tail, or
        # it fits in the first level of the root node.
        p_next = pvec()
        count = 0
        c = 0
        print "=== p_next 1: " + str(p_next)
        for x in range(1): # 99
            a = p_next
            p_next = p_next.append(x)
            print "=== p_next 1: " + str(p_next) + ", a: " + str(a)

            count += 1
            c+=1
            for y in range(0): # x+1
                count += 1
                self.assertEqual(p_next[y], y)

    def test_random_insert_in_vector(self):
        print("Start 2")

        x = pvec(range(2)) # 2000
        for i in x:
            y = x.assoc(i, x[i] * 10000)
#            self.assertEqual(y[i], x[i] * 10000)

    def test_random_insert_end_of_vector(self):
        print("Start 3")

        x = pvec(range(0)) # 20
        y = x.assoc(0, 200)
        self.assertEqual(y[0], 200)
#        self.assertEqual(y[1], 200)

    def test_random_insert_out_of_bounds(self):
        print("Start 4")

        x = pvec()
        self.assertRaises(IndexError, x.assoc, 21, 200)

    def test_construction_with_argument(self):
        print("Start 5")

 #       x = pvec(range(2000))
 #       for i in x:
 #           self.assertEqual(i, x[i])

    def test_construction_performance(self):
        print("Start 6")

#        x = pvec(range(200))

    def xtest_infinity(self):
        print "Starting to tests infinity"

#        while True:
        x = pvec()
        print("Start")
        for z in range(10000000):
            x = x.append(z)
        print("Stop")


    def test_appends_to_large_sized_vectors(self):
        print("Start 7")

        # Tests appends where the inserts do not fit within the first level
        # of the root but must be pushed further down the tree.
#        p_next = pvec()
#        size = 32 * 32 * 32 + 32
#        for x in range(size):
#            p_next = p_next.append(x)
#            self.assertEqual(p_next[x], x)
#
#        for x in range(size):
#            self.assertEqual(p_next[x], x)

    def xtest_pvec_is_a_collection(self):
        print("Start 8")

        # Check that inheritance works as expected
        assert isinstance(pvec(), Sequence)

    # TODO Investigate why there are segmentation faults when these functions are removed
    def xtest_2_random_insert_out_of_bounds(self):
        print "Hej igen"

    def xtest_3_random_insert_out_of_bounds(self):
        print "Hej igen"

if __name__ == '__main__':
#    import cProfile
#    cProfile.run('insert_in_vector()')
    unittest.main()
