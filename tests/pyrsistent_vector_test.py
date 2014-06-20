import pytest

@pytest.fixture(scope='session', params=['pyrsistent', 'pvectorc'])
def pvector(request):
    m = pytest.importorskip(request.param)
    return m._pvector


def test_literalish_works():
    from pyrsistent import pvector, v
    assert v() is pvector()
    assert v(1, 2) == pvector([1, 2])


def test_empty_initialization(pvector):
    seq = pvector()
    assert len(seq) == 0

    with pytest.raises(IndexError):
        x = seq[0]


def test_initialization_with_one_element(pvector):
    seq = pvector([3])
    assert len(seq) == 1
    assert seq[0] == 3


def test_append_works_and_does_not_affect_original_within_tail(pvector):
    seq1 = pvector([3])
    seq2 = seq1.append(2)

    assert len(seq1) == 1
    assert seq1[0] == 3

    assert len(seq2) == 2
    assert seq2[0] == 3
    assert seq2[1] == 2


def test_append_works_and_does_not_affect_original_outside_tail(pvector):
    original = pvector([])
    seq = original

    for x in range(33):
        seq = seq.append(x)

    assert len(seq) == 33
    assert seq[0] == 0
    assert seq[31] == 31
    assert seq[32] == 32

    assert len(original) == 0


def test_append_when_root_overflows(pvector):
    seq = pvector([])

    for x in range(32 * 33):
        seq = seq.append(x)

    seq = seq.append(10001)

    for i in range(32 * 33):
        assert seq[i] == i

    assert seq[32 * 33] == 10001


def test_multi_level_sequence(pvector):
    seq = pvector(range(8000))
    seq2 = seq.append(11)

    assert seq[5] == 5
    assert seq2[7373] == 7373
    assert seq2[8000] == 11


def test_multi_level_sequence_from_iterator(pvector):
    seq = pvector(iter(range(8000)))
    seq2 = seq.append(11)

    assert seq[5] == 5
    assert seq2[7373] == 7373
    assert seq2[8000] == 11


def test_random_insert_within_tail(pvector):
    seq = pvector([1, 2, 3])

    seq2 = seq.assoc(1, 4)

    assert seq2[1] == 4
    assert seq[1] == 2


def test_random_insert_outside_tail(pvector):
    seq = pvector(range(20000))

    seq2 = seq.assoc(19000, 4)

    assert seq2[19000] == 4
    assert seq[19000] == 19000


def test_insert_beyond_end(pvector):
    seq = pvector(range(2))
    seq2 = seq.assoc(2, 50)    
    assert seq2[2] == 50

    with pytest.raises(IndexError):
        seq2.assoc(19, 4)


def test_iteration(pvector):
    y = 0
    seq = pvector(range(2000))
    for x in seq:
        assert x == y
        y += 1

    assert y == 2000


def test_zero_extend(pvector):
    the_list = []
    seq = pvector()
    seq2 = seq.extend(the_list)
    assert seq == seq2


def test_short_extend(pvector):
    # Extend within tail length
    the_list = [1, 2]
    seq = pvector()
    seq2 = seq.extend(the_list)

    assert len(seq2) == len(the_list)
    assert seq2[0] == the_list[0]
    assert seq2[1] == the_list[1]


def test_long_extend(pvector):
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


def test_slicing_zero_length_range(pvector):
    seq = pvector(range(10))
    seq2 = seq[2:2]

    assert len(seq2) == 0


def test_slicing_range(pvector):
    seq = pvector(range(10))
    seq2 = seq[2:4]

    assert list(seq2) == [2, 3]


def test_slice_identity(pvector):
    # Pvector is immutable, no need to make a copy!
    seq = pvector(range(10))

    assert seq is seq[::]


def test_slicing_range_with_step(pvector):
    seq = pvector(range(100))
    seq2 = seq[2:12:3]

    assert list(seq2) == [2, 5, 8, 11]


def test_slicing_no_range_but_step(pvector):
    seq = pvector(range(10))
    seq2 = seq[::2]

    assert list(seq2) == [0, 2, 4, 6, 8]


def test_slicing_reverse(pvector):
    seq = pvector(range(10))
    seq2 = seq[::-1]

    assert seq2[0] == 9
    assert seq2[1] == 8
    assert len(seq2) == 10

    seq3 = seq[-3: -7: -1]
    assert seq3[0] == 7
    assert seq3[3] == 4
    assert len(seq3) == 4


def test_addition(pvector):
    v = pvector([1, 2]) + pvector([3, 4])

    assert list(v) == [1, 2, 3, 4]


def test_slicing_reverse(pvector):
    seq = pvector(range(10))
    seq2 = seq[::-1]

    assert seq2[0] == 9
    assert seq2[1] == 8
    assert len(seq2) == 10

    seq3 = seq[-3: -7: -1]
    assert seq3[0] == 7
    assert seq3[3] == 4
    assert len(seq3) == 4


def test_sorted(pvector):
    seq = pvector([5, 2, 3, 1])
    assert [1, 2, 3, 5] == sorted(seq)


def test_boolean_conversion(pvector):
    assert not bool(pvector())
    assert bool(pvector([1]))


def test_access_with_negative_index(pvector):
    seq = pvector([1, 2, 3, 4])

    assert seq[-1] == 4
    assert seq[-4] == 1


def test_index_error_positive(pvector):
    with pytest.raises(IndexError):
        x = pvector([1, 2, 3])[3]


def test_index_error_negative(pvector):
    with pytest.raises(IndexError):
        x = pvector([1, 2, 3])[-4]


def test_is_sequence(pvector):
    from collections import Sequence
    assert isinstance(list(), Sequence)
    assert isinstance(pvector(), Sequence)


def test_empty_repr(pvector):
    assert str(pvector()) == "()"


def test_non_empty_repr(pvector):
    v = pvector([1, 2, 3])
    assert str(v) == "(1, 2, 3)"

    # There's some state that needs to be reset between calls in the native version,
    # test that multiple invocations work.
    assert str(v) == "(1, 2, 3)"


def test_repr_when_contained_object_contains_reference_to_self(pvector):
    x = [1, 2, 3]
    v = pvector([1, 2, x])
    x.append(v)
    assert str(v) == '(1, 2, [1, 2, 3, (...)])'

    # Run a GC to provoke any potential misbehavior
    import gc
    gc.collect()


def test_is_hashable(pvector):
    v = pvector([1, 2, 3])
    v2 = pvector([1, 2, 3])

    assert hash(v) == hash(v2)


def test_refuses_to_hash_when_members_are_unhashable(pvector):
    v = pvector([1, 2, [1, 2]])

    with pytest.raises(TypeError):
        hash(v)


def test_compare_same_vectors(pvector):
    v = pvector([1, 2])
    assert v == v
    assert pvector() == pvector()


def test_compare_with_other_type_of_object(pvector):
    assert pvector([1, 2]) != 'foo'


def test_compare_equal_vectors(pvector):
    v1 = pvector([1, 2])
    v2 = pvector([1, 2])
    assert v1 == v2
    assert v1 >= v2
    assert v1 <= v2


def test_compare_different_vectors_same_size(pvector):
    v1 = pvector([1, 2])
    v2 = pvector([1, 3])
    assert v1 != v2


def test_compare_different_vectors_different_sizes(pvector):
    v1 = pvector([1, 2])
    v2 = pvector([1, 2, 3])
    assert v1 != v2


def test_compare_lt_gt(pvector):
    v1 = pvector([1, 2])
    v2 = pvector([1, 2, 3])
    assert v1 < v2
    assert v2 > v1


def test_repeat(pvector):
    v = pvector([1, 2])
    assert 5 * pvector() is pvector()
    assert v is 1 * v
    assert 0 * v is pvector()
    assert 2 * pvector([1, 2]) == pvector([1, 2, 1, 2])
    assert -3 * pvector([1, 2]) is pvector()
