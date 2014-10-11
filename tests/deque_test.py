import pytest
from pyrsistent import pdeque


def test_basic_right_and_left():
    x = pdeque([1, 2])

    assert x.right == 2
    assert x.left == 1


def test_pop():
    x = pdeque([1, 2, 3, 4]).pop()
    assert x.right == 3
    assert x.left == 1

    x = x.pop()
    assert x.right == 2
    assert x.left == 1

    x = x.pop()
    assert x.right == 1
    assert x.left == 1

    x = x.pop()
    assert x == pdeque()

def test_popleft():
    x = pdeque([1, 2, 3, 4]).popleft()
    assert x.left == 2
    assert x.right == 4

    x = x.popleft()
    assert x.left == 3
    assert x.right == 4

    x = x.popleft()
    assert x.right == 4
    assert x.left == 4

    x = x.popleft()
    assert x == pdeque()

def test_left_on_empty_deqeue():
    with pytest.raises(IndexError):
        pdeque().left


def test_right_on_empty_deqeue():
    with pytest.raises(IndexError):
        pdeque().right


def test_pop_empty_deque_returns_empty_queue():
    # The other option is to throw an index error, this is what feels best for now though
    assert pdeque().pop() is pdeque()
    assert pdeque().popleft() is pdeque()


def test_str():
    assert str(pdeque([1, 2, 3])) == 'pdeque([1, 2, 3])'
    assert str(pdeque([])) == 'pdeque([])'


def test_append():
    assert pdeque([1, 2]).append(3).append(4) == pdeque([1, 2, 3, 4])


def test_appendleft():
    assert pdeque([2, 1]).appendleft(3).appendleft(4) == pdeque([4, 3, 2, 1])


def test_extend():
    assert pdeque([1, 2]).extend([3, 4]) == pdeque([1, 2, 3, 4])


def test_extendleft():
    assert pdeque([2, 1]).extendleft([3, 4]) == pdeque([4, 3, 2, 1])


def test_count():
    x = pdeque([1, 2, 3, 2, 1])
    assert x.count(1) == 2
    assert x.count(2) == 2


def test_remove():
    assert pdeque([1, 2, 3, 4]).remove(2) == pdeque([1, 3, 4])
    assert pdeque([1, 2, 3, 4]).remove(4) == pdeque([1, 2, 3])

    # Right list must be reversed before removing element
    assert pdeque([1, 2, 3, 3, 4, 5, 4, 6]).remove(4) == pdeque([1, 2, 3, 3, 5, 4, 6])


def test_remove_element_missing():
    with pytest.raises(ValueError):
        pdeque().remove(2)

    with pytest.raises(ValueError):
        pdeque([1, 2, 3]).remove(4)