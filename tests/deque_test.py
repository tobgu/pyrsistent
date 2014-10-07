import pytest
from pyrsistent import pdeque


def test_basic_right_and_left():
    x = pdeque([1, 2])

    assert x.right == 2
    assert x.left == 1


def test_pop():
    x = pdeque([1, 2]).pop()

    assert x.right == 1
    assert x.left == 1


def test_popleft():
    x = pdeque([1, 2]).popleft()

    assert x.left == 2
    assert x.right == 2


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