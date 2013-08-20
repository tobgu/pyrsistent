# from pyrsistent import pvector 
from collections import Sequence
from pyrsistentc import pvec

import unittest

class TestPyVec(unittest.TestCase):
    def insert_in_vector(self):
        m = pvector(range(50000))

    def test_appends_to_small_and_medium_sized_vectors(self):
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

     
    def test_pvec_is_a_collection(self):
        # Check that inheritance works as expected
        assert isinstance(pvec(), Sequence)
    
        
if __name__ == '__main__':
#    import cProfile
#    cProfile.run('insert_in_vector()')
    unittest.main()
