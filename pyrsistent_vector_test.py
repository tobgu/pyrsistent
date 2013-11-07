from pyrsistent import pvector, pvec

import pytest


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


def test_vector_to_list():
    l = range(2000)
    seq = pvector(l)

    assert seq.tolist() == l


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


def test_slicing_range():
    seq = pvector(range(10))
    seq2 = seq[2:4]

    assert seq2[0] == 2
    assert seq2[1] == 3


def test_slicing_step():
    seq = pvector(range(10))
    seq2 = seq[::2]

    assert seq2[0] == 0
    assert seq2[1] == 2
    assert len(seq2) == 5


def test_to_list():
    l = list(range(32*32 + 64 + 7))
    v = pvector(l)

    assert l == v.tolist()


def test_addition():
    v = pvec(1, 2) + pvec(3, 4)

    assert v.tolist() == [1, 2, 3, 4]
    assert list(v) == v.tolist()


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


def test_to_string():
    seq = pvector(range(2000))

    assert str(seq) == str(range(2000))
    assert seq.tostr() == str(range(2000))