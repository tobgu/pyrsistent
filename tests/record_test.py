import pickle
import pytest
from pyrsistent import PRecord, field, InvariantException

class ARecord(PRecord):
    x = field(type=(int, float))
    y = field()


def test_create():
    r = ARecord(x=1, y='foo')
    assert r.x == 1
    assert r.y == 'foo'
    assert isinstance(r, ARecord)


def test_correct_assignment():
    r = ARecord(x=1, y='foo')
    r2 = r.set('x', 2.0)
    r3 = r2.set('y', 'bar')

    assert r2 == {'x': 2.0, 'y': 'foo'}
    assert r3 == {'x': 2.0, 'y': 'bar'}
    assert isinstance(r3, ARecord)


def test_direct_assignment_not_possible():
    with pytest.raises(AttributeError):
        ARecord().x = 1


def test_cannot_assign_undeclared_fields():
    with pytest.raises(AttributeError):
        ARecord().set('z', 5)


def test_cannot_assign_wrong_type_to_fields():
    with pytest.raises(TypeError):
        ARecord().set('x', 'foo')


def test_cannot_construct_with_undeclared_fields():
    with pytest.raises(AttributeError):
        ARecord(z=5)


def test_cannot_construct_with_fields_of_wrong_type():
    with pytest.raises(TypeError):
        ARecord(x='foo')


def test_support_record_inheritance():
    class BRecord(ARecord):
        z = field()

    r = BRecord(x=1, y='foo', z='bar')

    assert isinstance(r, BRecord)
    assert isinstance(r, ARecord)
    assert r == {'x': 1, 'y': 'foo', 'z': 'bar'}


def test_single_type_spec():
    class A(PRecord):
        x = field(type=int)

    r = A(x=1)
    assert r.x == 1

    with pytest.raises(TypeError):
        r.set('x', 'foo')


def test_remove():
    r = ARecord(x=1, y='foo')
    r2 = r.remove('y')

    assert isinstance(r2, ARecord)
    assert r2 == {'x': 1}


def test_field_invariant_must_hold():
    class BRecord(PRecord):
        x = field(invariant=lambda x: (x > 1, 'x too small'))
        y = field(mandatory=True)

    try:
        BRecord(x=1)
        assert False
    except InvariantException as e:
        assert e.error_codes == ('x too small',)
        assert e.missing_fields == ('y',)

def test_global_invariant_must_hold():
    class BRecord(PRecord):
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


def test_set_multiple_fields():
    a = ARecord(x=1, y='foo')
    b = a.set(x=2, y='bar')

    assert b == {'x': 2, 'y': 'bar'}


def test_initial_value():
    class BRecord(PRecord):
        x = field(initial=1)
        y = field(initial=2)

    a = BRecord()
    assert a.x == 1
    assert a.y == 2


def test_type_specification_must_be_a_type():
    with pytest.raises(TypeError):
        class BRecord(PRecord):
            x = field(type=1)


def test_initial_must_be_of_correct_type():
    with pytest.raises(TypeError):
        class BRecord(PRecord):
            x = field(type=int, initial='foo')


def test_invariant_must_be_callable():
    with pytest.raises(TypeError):
        class BRecord(PRecord):
            x = field(invariant='foo')


def test_global_invariants_are_inherited():
    class BRecord(PRecord):
        __invariant__ = lambda r: (r.x % r.y == 0, 'modulo')
        x = field()
        y = field()

    class CRecord(BRecord):
        __invariant__ = lambda r: (r.x > r.y, 'size')

    try:
        CRecord(x=5, y=3)
        assert False
    except InvariantException as e:
        assert e.error_codes == ('modulo',)

def test_global_invariants_must_be_callable():
    with pytest.raises(TypeError):
        class CRecord(PRecord):
            __invariant__ = 1

#def test_pickling():
#    ARecord = precord('a', b=(int, float))
#    x = ARecord(a='bar', b=2.0)
#    y = pickle.loads(pickle.dumps(x, -1))
#
#    assert x == y
#    assert isinstance(y, PRecord)

#    # Field and type checks should remain
#    with pytest.raises(AttributeError):
#        ARecord(c='asd')
#
#    with pytest.raises(TypeError):
#        ARecord(b='asd')
#