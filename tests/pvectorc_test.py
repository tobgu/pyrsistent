from collections import Sequence
from pvectorc import pvec as pvector
import pytest
import time


def pvec(*args):
    return pvector(args)


def xtest_initilization_speed():
    print "Before: %s" % time.time()
    seq = pvector(xrange(1000000))
    print "After: %s" % time.time()
    assert True

    # 0.33 - 0.36 s


def test_empty_initialization():
    seq = pvector()
    assert len(seq) == 0

    with pytest.raises(IndexError):
        x = seq[0]


def test_initialization_with_one_element():
    seq = pvector([3])
    assert len(seq) == 1
    assert seq[0] == 3


def test_append_works_and_does_not_affect_original_within_tail():
    seq1 = pvector([3])
    seq2 = seq1.append(2)

    assert len(seq1) == 1
    assert seq1[0] == 3

    assert len(seq2) == 2
    assert seq2[0] == 3
    assert seq2[1] == 2


def test_append_works_and_does_not_affect_original_outside_tail():
    original = pvector([])
    seq = original

    for x in range(33):
        seq = seq.append(x)

    assert len(seq) == 33
    assert seq[0] == 0
    assert seq[31] == 31
    assert seq[32] == 32

    assert len(original) == 0


def test_append_when_root_overflows():
    seq = pvector([])

    for x in range(32 * 33):
        seq = seq.append(x)

    seq = seq.append(10001)

    for i in range(32 * 33):
        assert seq[i] == i

    assert seq[32 * 33] == 10001


def test_multi_level_sequence():
    seq = pvector(range(8000))
    seq2 = seq.append(11)

    assert seq[5] == 5
    assert seq2[7373] == 7373
    assert seq2[8000] == 11


def test_multi_level_sequence_from_iterator():
    seq = pvector(iter(range(8000)))
    seq2 = seq.append(11)

    assert seq[5] == 5
    assert seq2[7373] == 7373
    assert seq2[8000] == 11


def test_random_insert_within_tail():
    seq = pvector([1, 2, 3])

    seq2 = seq.assoc(1, 4)

    assert seq2[1] == 4
    assert seq[1] == 2


def test_random_insert_outside_tail():
    seq = pvector(range(20000))

    seq2 = seq.assoc(19000, 4)

    assert seq2[19000] == 4
    assert seq[19000] == 19000


def test_insert_beyond_end():
    seq = pvector(range(2))
    seq2 = seq.assoc(2, 50)    
    assert seq2[2] == 50

    with pytest.raises(IndexError):
        seq2.assoc(19, 4)


def test_string_representation():
    pass


def test_iteration():
    y = 0
    seq = pvector(range(2000))
    for x in seq:
        assert x == y
        y += 1

    assert y == 2000


def test_zero_extend():
    the_list = []
    seq = pvector()
    seq2 = seq.extend(the_list)
    assert seq == seq2


def test_short_extend():
    # Extend within tail length
    the_list = [1, 2]
    seq = pvector()
    seq2 = seq.extend(the_list)

    assert len(seq2) == len(the_list)
    assert seq2[0] == the_list[0]
    assert seq2[1] == the_list[1]


def test_long_extend():
    # Multi level extend
    seq = pvector()
    length = 2137

    # Extend from scratch
    seq2 = seq.extend(range(length))
    assert len(seq2) == length
    for i in range(length):
        assert seq2[i] == i

    # Extend already filled vector
    seq3 = seq2.extend(range(length, length + 5))
    assert len(seq3) == length + 5
    for i in range(length + 5):
        assert seq3[i] == i

    # Check that the original vector is still intact
    assert len(seq2) == length
    for i in range(length):
        assert seq2[i] == i


def test_slicing_zero_length_range():
    seq = pvector(range(10))
    seq2 = seq[2:2]

    assert len(seq2) == 0


def test_slicing_range():
    seq = pvector(range(10))
    seq2 = seq[2:4]

    assert list(seq2) == [2, 3]


def test_slice_identity():
    # Pvector is immutable, no need to make a copy!
    seq = pvector(range(10))

    assert seq is seq[::]


def test_slicing_range_with_step():
    seq = pvector(range(100))
    seq2 = seq[2:12:3]

    assert list(seq2) == [2, 5, 8, 11]


def test_no_range_but_step():
    seq = pvector(range(10))
    seq2 = seq[::2]

    assert list(seq2) == [0, 2, 4, 6, 8]


def test_slicing_reverse():
    seq = pvector(range(10))
    seq2 = seq[::-1]

    assert seq2[0] == 9
    assert seq2[1] == 8
    assert len(seq2) == 10

    seq3 = seq[-3: -7: -1]
    assert seq3[0] == 7
    assert seq3[3] == 4
    assert len(seq3) == 4


def test_addition():
    v = pvec(1, 2) + pvec(3, 4)

    assert list(v) == [1, 2, 3, 4]


def xtest_to_string():
    seq = pvector(range(2000))

    assert str(seq) == str(range(2000))


def test_sorted():
    seq = pvec(5, 2, 3, 1)
    assert [1, 2, 3, 5] == sorted(seq)


def test_boolean_conversion():
    assert not bool(pvec())
    assert bool(pvec(1))


def test_access_with_negative_index():
    seq = pvector([1, 2, 3, 4])

    assert seq[-1] == 4
    assert seq[-4] == 1


def test_index_error_positive():
    with pytest.raises(IndexError):
        x = pvec(1, 2, 3)[3]


def test_index_error_negative():
    with pytest.raises(IndexError):
        x = pvec(1, 2, 3)[-4]


def test_is_sequence():
    assert isinstance(list(), Sequence)
    assert isinstance(pvec(), Sequence)


def test_empty_repr():
    assert str(pvec()) == "()"


def test_non_empty_repr():
    v = pvec(1, 2, 3)
    assert str(v) == "(1, 2, 3)"
    assert str(v) == "(1, 2, 3)"


def test_repr_when_contained_object_contains_reference_to_self():
    x = [1, 2, 3]
    v = pvector([1, 2, x])
    x.append(v)
    assert str(v) == '(1, 2, [1, 2, 3, (...)])'

    # Run a GC to provoke any potential misbehavior
    import gc
    gc.collect()


def test_is_hashable():
    v = pvec(1, 2, 3)
    v2 = pvec(1, 2, 3)

    assert hash(v) == hash(v2)


def test_refuses_to_hash_when_members_are_unhashable():
    v = pvec(1, 2, [1, 2])

    with pytest.raises(TypeError):
        hash(v)


def test_compare_same_vectors():
    v = pvector([1, 2])
    assert v == v
    assert pvector() == pvector()


def test_compare_with_other_type_of_object():
    assert pvector([1, 2]) != 'foo'


def test_compare_equal_vectors():
    v1 = pvec(1, 2)
    v2 = pvec(1, 2)
    assert v1 == v2
    assert v1 >= v2
    assert v1 <= v2


def test_compare_different_vectors_same_size():
    v1 = pvec(1, 2)
    v2 = pvec(1, 3)
    assert v1 != v2


def test_compare_different_vectors_different_sizes():
    v1 = pvec(1, 2)
    v2 = pvec(1, 2, 3)
    assert v1 != v2


def test_compare_lt_gt():
    v1 = pvec(1, 2)
    v2 = pvec(1, 2, 3)
    assert v1 < v2
    assert v2 > v1


def test_repeat():
    v = pvec(1, 2)
    assert 5 * pvec() is pvec()
    assert v is 1 * v
    assert 0 * v is pvec()
    assert 2 * pvec(1, 2) == pvec(1, 2, 1, 2)
    assert -3 * pvec(1, 2) is pvec()

