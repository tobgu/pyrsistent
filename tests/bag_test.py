import pytest

from pyrsistent import b, pbag


def test_literalish_works():
    assert b(1, 2) == pbag([1, 2])

def test_empty_bag():
    """
    creating an empty pbag returns a singleton.

    Note that this should NOT be relied upon in application code.
    """
    assert b() is b()

def test_supports_hash():
    assert hash(b(1, 2)) == hash(b(2, 1))

def test_hash_in_dict():
    assert {b(1,2,3,3): "hello"}[b(3,3,2,1)] == "hello"

def test_empty_truthiness():
    assert b(1)
    assert not b()


def test_repr_empty():
    assert repr(b()) == 'pbag([])'

def test_repr_elements():
    assert repr(b(1, 2)) in ('pbag([1, 2])', 'pbag([2, 1])')


def test_add_empty():
    assert b().add(1) == b(1)

def test_remove_final():
    assert b().add(1).remove(1) == b()

def test_remove_nonfinal():
    assert b().add(1).add(1).remove(1) == b(1)

def test_remove_nonexistent():
    with pytest.raises(KeyError) as excinfo:
        b().remove(1)
    assert str(excinfo.exconly()) == 'KeyError: 1'


def test_eq_empty():
    assert b() == b()

def test_neq():
    assert b(1) != b()

def test_eq_same_order():
    assert b(1, 2, 1) == b(1, 2, 1)

def test_eq_different_order():
    assert b(2, 1, 2) == b(1, 2, 2)


def test_count_non_existent():
    assert b().count(1) == 0

def test_count_unique():
    assert b(1).count(1) == 1

def test_count_duplicate():
    assert b(1, 1).count(1) == 2


def test_length_empty():
    assert len(b()) == 0

def test_length_unique():
    assert len(b(1)) == 1

def test_length_duplicates():
    assert len(b(1, 1)) == 2

def test_length_multiple_elements():
    assert len(b(1, 1, 2, 3)) == 4


def test_iter_duplicates():
    assert list(b(1, 1)) == [1, 1]

def test_iter_multiple_elements():
    assert list(b(1, 2, 2)) in ([1, 2, 2], [2, 2, 1])

def test_contains():
    assert 1 in b(1)

def test_not_contains():
    assert 1 not in b(2)

def test_add():
    assert b(3, 3, 3, 2, 2, 1) + b(4, 3, 2, 1) == b(4,
                                                    3, 3, 3, 3,
                                                    2, 2, 2,
                                                    1, 1)

def test_sub():
    assert b(1, 2, 3, 3) - b(3, 4) == b(1, 2, 3)

def test_or():
    assert b(1, 2, 2, 3, 3, 3) | b(1, 2, 3, 4, 4) == b(1,
                                                       2, 2,
                                                       3, 3, 3,
                                                       4, 4)

def test_and():
    assert b(1, 2, 2, 3, 3, 3) & b(2, 3, 3, 4) == b(2, 3, 3)


def test_pbag_is_unorderable():
    with pytest.raises(TypeError):
        _ = b(1) < b(2)  # type: ignore

    with pytest.raises(TypeError):
        _ = b(1) <= b(2)  # type: ignore

    with pytest.raises(TypeError):
        _ = b(1) > b(2)  # type: ignore

    with pytest.raises(TypeError):
        _ = b(1) >= b(2)  # type: ignore


def test_supports_weakref():
    import weakref
    weakref.ref(b(1))


def test_update():
    assert pbag([1, 2, 2]).update([3, 3, 4]) == pbag([1, 2, 2, 3, 3, 4])


def test_update_no_elements():
    b = pbag([1, 2, 2])
    assert b.update([]) is b


def test_iterable():
    """
    PBags can be created from iterables even though they can't be len() hinted.
    """

    assert pbag(iter("a")) == pbag(iter("a"))


class FalseIterable:
    def __iter__(self):
        return iter([0, 0, 1])

    def __bool__(self):
        return False


class NoTruthIterable(FalseIterable):
    def __bool__(self):
        raise ValueError('ambiguous iterable truth value')


@pytest.mark.parametrize('factory', [FalseIterable, NoTruthIterable])
def test_bag_consumes_iterables_without_testing_truth(factory):
    assert pbag(factory()) == b(0, 0, 1)


@pytest.mark.parametrize('factory', [FalseIterable, NoTruthIterable])
def test_bag_update_consumes_iterables_without_testing_truth(factory):
    original = b(2)
    assert original.update(factory()) == b(0, 0, 1, 2)
    assert original == b(2)


def test_bag_empty_iterators_remain_empty_and_leave_original_unchanged():
    assert pbag(iter(())) == b()
    original = b(1)
    assert original.update(iter(())) == original
