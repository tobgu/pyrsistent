import pickle
import datetime
import pytest
from pyrsistent import PRecord, field, InvariantException, ny


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
        assert e.missing_fields == ('BRecord.y',)

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

def test_repr():
    r = ARecord(x=1, y=2)
    assert repr(r) == 'ARecord(x=1, y=2)' or repr(r) == 'ARecord(y=2, x=1)'

def test_factory():
    class BRecord(PRecord):
        x = field(type=int, factory=int)

    assert BRecord(x=2.5) == {'x': 2}

def test_factory_must_be_callable():
    with pytest.raises(TypeError):
        class BRecord(PRecord):
            x = field(type=int, factory=1)

def test_nested_record_construction():
    class BRecord(PRecord):
        x = field(int, factory=int)

    class CRecord(PRecord):
        a = field()
        b = field(type=BRecord)

    r = CRecord.create({'a': 'foo', 'b': {'x': '5'}})
    assert isinstance(r, CRecord)
    assert isinstance(r.b, BRecord)
    assert r == {'a': 'foo', 'b': {'x': 5}}

def test_pickling():
    x = ARecord(x=2.0, y='bar')
    y = pickle.loads(pickle.dumps(x, -1))

    assert x == y
    assert isinstance(y, ARecord)

def test_all_invariant_errors_reported():
    class BRecord(PRecord):
        x = field(factory=int, invariant=lambda x: (x >= 0, 'x negative'))
        y = field(mandatory=True)

    class CRecord(PRecord):
        a = field(invariant=lambda x: (x != 0, 'a zero'))
        b = field(type=BRecord)

    try:
        CRecord.create({'a': 0, 'b': {'x': -5}})
        assert False
    except InvariantException as e:
        assert set(e.error_codes) == set(['x negative', 'a zero'])
        assert e.missing_fields == ('BRecord.y',)


def test_precord_factory_method_is_idempotent():
    class BRecord(PRecord):
        x = field()
        y = field()

    r = BRecord(x=1, y=2)
    assert BRecord.create(r) is r

def test_serialize():
    class BRecord(PRecord):
        d = field(type=datetime.date,
                  factory=lambda d: datetime.datetime.strptime(d, "%d%m%Y").date(),
                  serializer=lambda format, d: d.strftime('%Y-%m-%d') if format=='ISO' else d.strftime('%d%m%Y'))

    assert BRecord(d='14012015').serialize('ISO') == {'d': '2015-01-14'}
    assert BRecord(d='14012015').serialize('other') == {'d': '14012015'}

def test_nested_serialize():
    class BRecord(PRecord):
        d = field(serializer=lambda format, d: format)

    class CRecord(PRecord):
        b = field()

    serialized = CRecord(b=BRecord(d='foo')).serialize('bar')

    assert serialized == {'b': {'d': 'bar'}}
    assert isinstance(serialized, dict)

def test_serializer_must_be_callable():
    with pytest.raises(TypeError):
        class CRecord(PRecord):
            x = field(serializer=1)

def test_transform_without_update_returns_same_precord():
    r = ARecord(x=2.0, y='bar')
    assert r.transform([ny], lambda x: x) is r