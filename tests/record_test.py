from pyrsistent import record, PRecord


def test_multiple_types_and_transplant():
    ARecord = record('a', b={int, float})
    foo = ARecord(a=1)
    assert isinstance(foo.set('b', 1), PRecord)
    assert isinstance(foo.set('b', 1.0), PRecord)
    try:
        foo.set('b', 'asd')
        assert False
    except AssertionError:
        pass


def test_single_type_and_transplant():
    ARecord = record(b=int)
    foo = ARecord()
    assert isinstance(foo.set('b', 1), PRecord)
    try:
        foo.set('b', 'asd')
        assert False
    except AssertionError:
        pass


def test_untyped_field():
    ARecord = record('a')
    foo = ARecord(a=1)
    foo.set('a', 1)
    foo.set('a', 1.0)
    foo.set('a', 'asd')


def test_constructor():
    ARecord = record(b=int)
    ARecord(b=1)
    try:
        ARecord(a=1)
        assert False
    except AssertionError:
        pass

