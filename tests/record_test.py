import pytest
from pyrsistent import precord, PRecord


def test_multiple_types_and_transplant():
    ARecord = precord('a', b=set([int, float]))
    foo = ARecord(a=1)
    assert isinstance(foo.set('b', 1), PRecord)
    assert isinstance(foo.set('b', 1.0), PRecord)
    with pytest.raises(TypeError):
        foo.set('b', 'asd')


def test_single_type_and_transplant():
    ARecord = precord(b=int)
    foo = ARecord()
    assert isinstance(foo.set('b', 1), PRecord)
    with pytest.raises(TypeError):
        foo.set('b', 'asd')
    with pytest.raises(AttributeError):
        foo.set('q', 'asd')


def test_untyped_field():
    ARecord = precord('a')
    foo = ARecord(a=1)
    foo.set('a', 1)
    foo.set('a', 1.0)
    foo.set('a', 'asd')


def test_constructor():
    ARecord = precord(b=int)
    ARecord(b=1)
    with pytest.raises(TypeError):
        ARecord(b='asd')
    with pytest.raises(AttributeError):
        ARecord(a=1)

