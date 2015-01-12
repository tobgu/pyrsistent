import pickle
import pytest
from pyrsistent import precord, PRecord, PRec, field, InvariantException


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

class ARecord(PRec):
    x = field(type=(int, float))
    y = field()


def test_prec_create():
    r = ARecord(x=1, y='foo')
    assert r.x == 1
    assert r.y == 'foo'
    assert isinstance(r, ARecord)


def test_prec_correct_assignment():
    r = ARecord(x=1, y='foo')
    r2 = r.set('x', 2.0)
    r3 = r2.set('y', 'bar')

    assert r2 == {'x': 2.0, 'y': 'foo'}
    assert r3 == {'x': 2.0, 'y': 'bar'}
    assert isinstance(r3, ARecord)


def test_prec_direct_assignment_not_possible():
    with pytest.raises(AttributeError):
        ARecord().x = 1


def test_prec_cannot_assign_undeclared_fields():
    with pytest.raises(AttributeError):
        ARecord().set('z', 5)


def test_prec_cannot_assign_wrong_type_to_fields():
    with pytest.raises(TypeError):
        ARecord().set('x', 'foo')


def test_prec_cannot_construct_with_undeclared_fields():
    with pytest.raises(AttributeError):
        ARecord(z=5)


def test_prec_cannot_construct_with_fields_of_wrong_type():
    with pytest.raises(TypeError):
        ARecord(x='foo')


def test_prec_support_record_inheritance():
    class BRecord(ARecord):
        z = field()

    r = BRecord(x=1, y='foo', z='bar')

    assert isinstance(r, BRecord)
    assert isinstance(r, ARecord)
    assert r == {'x': 1, 'y': 'foo', 'z': 'bar'}


def test_prec_single_type_spec():
    class A(PRec):
        x = field(type=int)

    r = A(x=1)
    assert r.x == 1

    with pytest.raises(TypeError):
        r.set('x', 'foo')


def test_prec_remove():
    r = ARecord(x=1, y='foo')
    r2 = r.remove('y')

    assert isinstance(r2, ARecord)
    assert r2 == {'x': 1}


def test_prec_field_invariant_must_hold():
    class BRecord(PRec):
        x = field(invariant=lambda x: (x > 1, 'x too small'))
        y = field(mandatory=True)

    try:
        BRecord(x=1)
        assert False
    except InvariantException as e:
        assert e.error_codes == ('x too small',)
        assert e.missing_fields == ('y',)

def test_prec_global_invariant_must_hold():
    class BRecord(PRec):
        __invariant__ = lambda r: (r.x <= r.y, 'y smaller than x')
        x = field()
        y = field()

    BRecord(x=1, y=2)

    try:
        BRecord(x=2, y=1)
        assert False
    except InvariantException as e:
        assert e.error_codes == ('y smaller than x',)
        assert e.missing_fields == ()

def test_prec_set_multiple_fields():
    a = ARecord(x=1, y='foo')
    b = a.set(x=2, y='bar')

    assert b == {'x': 2, 'y': 'bar'}