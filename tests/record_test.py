import pickle
import pytest
from pyrsistent import precord, PRecord


def test_multiple_types_and_transplant():
    ARecord = precord('a', b=(int, float))
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


def test_remove():
    ARecord = precord('a')
    foo = ARecord(a=1)
    bar = foo.remove('a')

    assert bar == ARecord()
    assert isinstance(bar, PRecord)


def test_constructor():
    ARecord = precord(b=int)
    ARecord(b=1)

    with pytest.raises(TypeError):
        ARecord(b='asd')

    with pytest.raises(AttributeError):
        ARecord(a=1)


def test_repr_non_empty_record():
    ARecord = precord('a', b=(int, float))
    x = ARecord(a='bar', b=2.0)

    assert str(x) == "precord('a', b=(float, int,))(a='bar', b=2.0)"


def test_repr_empty_record():
    y = precord()()

    assert str(y) == "precord()()"


def test_pickling():
    ARecord = precord('a', b=(int, float))
    x = ARecord(a='bar', b=2.0)
    y = pickle.loads(pickle.dumps(x, -1))

    assert x == y
    assert isinstance(y, PRecord)

    # Field and type checks should remain
    with pytest.raises(AttributeError):
        ARecord(c='asd')

    with pytest.raises(TypeError):
        ARecord(b='asd')
