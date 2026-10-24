import pickle
import pytest
from pyrsistent import plist, l


def test_literalish_works():
    assert l(1, 2, 3) == plist([1, 2, 3])


def test_first_and_rest():
    pl = plist([1, 2])
    assert pl.first == 1
    assert pl.rest.first == 2
    assert pl.rest.rest is plist()


def test_instantiate_large_list():
    assert plist(range(1000)).first == 0


def test_iteration():
    assert list(plist()) == []
    assert list(plist([1, 2, 3])) == [1, 2, 3]


def test_cons():
    assert plist([1, 2, 3]).cons(0) == plist([0, 1, 2, 3])


def test_cons_empty_list():
    assert plist().cons(0) == plist([0])


def test_truthiness():
    assert plist([1])
    assert not plist()


def test_len():
    assert len(plist([1, 2, 3])) == 3
    assert len(plist()) == 0


def test_first_illegal_on_empty_list():
    with pytest.raises(AttributeError):
        plist().first


def test_rest_return_self_on_empty_list():
    assert plist().rest is plist()


def test_reverse():
    assert plist([1, 2, 3]).reverse() == plist([3, 2, 1])
    assert reversed(plist([1, 2, 3])) == plist([3, 2, 1])

    assert plist().reverse() == plist()
    assert reversed(plist()) == plist()


def test_inequality():
    assert plist([1, 2]) != plist([1, 3])
    assert plist([1, 2]) != plist([1, 2, 3])
    assert plist() != plist([1, 2, 3])


def test_repr():
    assert str(plist()) == "plist([])"
    assert str(plist([1, 2, 3])) == "plist([1, 2, 3])"


def test_indexing():
    assert plist([1, 2, 3])[2] == 3
    assert plist([1, 2, 3])[-1] == 3


def test_indexing_on_empty_list():
    with pytest.raises(IndexError):
        plist()[0]


def test_index_out_of_range():
    with pytest.raises(IndexError):
        plist([1, 2])[2]

    with pytest.raises(IndexError):
        plist([1, 2])[-3]

def test_index_invalid_type():
    with pytest.raises(TypeError) as e:
        plist([1, 2, 3])['foo']  # type: ignore

    assert 'cannot be interpreted' in str(e.value)


def test_slicing_take():
    assert plist([1, 2, 3])[:2] == plist([1, 2])


def test_slicing_take_out_of_range():
    assert plist([1, 2, 3])[:20] == plist([1, 2, 3])


def test_slicing_drop():
    li = plist([1, 2, 3])
    assert li[1:] is li.rest


def test_slicing_drop_out_of_range():
    assert plist([1, 2, 3])[3:] is plist()


def test_contains():
    assert 2 in plist([1, 2, 3])
    assert 4 not in plist([1, 2, 3])
    assert 1 not in plist()


def test_count():
    assert plist([1, 2, 1]).count(1) == 2
    assert plist().count(1) == 0


def test_index():
    assert plist([1, 2, 3]).index(3) == 2


def test_index_item_not_found():
    with pytest.raises(ValueError):
        plist().index(3)

    with pytest.raises(ValueError):
        plist([1, 2]).index(3)


def test_pickling_empty_list():
    assert pickle.loads(pickle.dumps(plist(), -1)) == plist()


def test_pickling_non_empty_list():
    assert pickle.loads(pickle.dumps(plist([1, 2, 3]), -1)) == plist([1, 2, 3])


def test_comparison():
    assert plist([1, 2]) < plist([1, 2, 3])
    assert plist([2, 1]) > plist([1, 2, 3])
    assert plist() < plist([1])
    assert plist([1]) > plist()


def test_comparison_with_other_type():
    assert plist() != []


def test_hashing():
    assert hash(plist([1, 2])) == hash(plist([1, 2]))
    assert hash(plist([1, 2])) != hash(plist([2, 1]))


def test_split():
    left_list, right_list = plist([1, 2, 3, 4, 5]).split(3)
    assert left_list == plist([1, 2, 3])
    assert right_list == plist([4, 5])


def test_split_no_split_occurred():
    x = plist([1, 2])
    left_list, right_list = x.split(2)
    assert left_list is x
    assert right_list is plist()


def test_split_empty_list():
    left_list, right_list = plist().split(2)
    assert left_list == plist()
    assert right_list == plist()


def test_remove():
    assert plist([1, 2, 3, 2]).remove(2) == plist([1, 3, 2])
    assert plist([1, 2, 3]).remove(1) == plist([2, 3])
    assert plist([1, 2, 3]).remove(3) == plist([1, 2])


def test_remove_missing_element():
    with pytest.raises(ValueError):
        plist([1, 2]).remove(3)

    with pytest.raises(ValueError):
        plist().remove(2)


def test_mcons():
    assert plist([1, 2]).mcons([3, 4]) == plist([4, 3, 1, 2])


def test_supports_weakref():
    import weakref
    weakref.ref(plist())
    weakref.ref(plist([1, 2]))


def test_iterable():
    """
    PLists can be created from iterables even though they can't be len()
    hinted.
    """

    assert plist(iter("a")) == plist(iter("a"))


class NonReflexive:
    def __eq__(self, other):
        return False


class EqualityRaises:
    def __eq__(self, other):
        raise RuntimeError('comparison called')


@pytest.mark.parametrize('item', [float('nan'), NonReflexive(), EqualityRaises()])
def test_equality_preserves_identical_elements(item):
    values = plist([0, item, 2])
    assert values == values
    assert values == plist([0, item, 2])
    assert not (values != plist([0, item, 2]))


@pytest.mark.parametrize('item', [float('nan'), NonReflexive()])
@pytest.mark.parametrize('position', [0, 1, 2])
def test_remove_identical_elements(item, position):
    elements = [0, 1, 2]
    elements[position] = item
    values = plist(elements)
    assert item in values
    assert values.count(item) == 1
    result = values.remove(item)
    assert list(result) == elements[:position] + elements[position + 1:]
    assert list(values) == elements


def test_distinct_nonreflexive_elements_remain_distinct():
    first, second = float('nan'), float('nan')
    assert plist([first]) != plist([second])
    with pytest.raises(ValueError):
        plist([first]).remove(second)


def test_distinct_elements_still_use_equality():
    class EqualValue:
        def __eq__(self, other):
            return isinstance(other, EqualValue)

    assert plist([EqualValue()]) == plist([EqualValue()])
    assert plist([EqualValue(), 2]).remove(EqualValue()) == plist([2])


def test_distinct_element_comparison_errors_propagate():
    with pytest.raises(RuntimeError, match='comparison called'):
        plist([EqualityRaises()]) == plist([object()])
    with pytest.raises(RuntimeError, match='comparison called'):
        plist([EqualityRaises()]).remove(object())


def test_remove_identical_element_does_not_call_equality():
    item = EqualityRaises()
    values = plist([item, 1])
    assert values.remove(item) == plist([1])
    assert values.first is item


def test_nan_hash_is_consistent_with_equality():
    item = float('nan')
    first = plist([item])
    second = plist([item])
    assert first == second
    assert hash(first) == hash(second)
    assert {first: 'found'}[second] == 'found'
