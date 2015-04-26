from collections import Hashable
import math
import pickle
import pytest
from pyrsistent import field, InvariantException
from pyrsistent import PClass


class Point(PClass):
    x = field(type=int, mandatory=True, invariant=lambda x: (x >= 0, 'X negative'))
    y = field(type=int, serializer=lambda formatter, y: formatter(y))
    z = field(type=int, initial=0)


def test_evolve_pclass_instance():
    p = Point(x=1, y=2)
    p2 = p.set(x=p.x+2)

    # Original remains
    assert p.x == 1
    assert p.y == 2

    # Evolved object updated
    assert p2.x == 3
    assert p2.y == 2

    p3 = p2.set('x', 4)
    assert p3.x == 4


def test_direct_assignment_not_possible():
    p = Point(x=1, y=2)

    with pytest.raises(AttributeError):
        p.x = 1

    with pytest.raises(AttributeError):
        setattr(p, 'x', 1)


def test_direct_delete_not_possible():
    p = Point(x=1, y=2)
    with pytest.raises(AttributeError):
        del p.x

    with pytest.raises(AttributeError):
        delattr(p, 'x')


def test_cannot_construct_with_undeclared_fields():
    with pytest.raises(AttributeError):
        Point(x=1, p=5)


def test_cannot_construct_with_wrong_type():
    with pytest.raises(TypeError):
        Point(x='a')


def test_cannot_construct_without_mandatory_fields():
    with pytest.raises(InvariantException):
        Point(y=1)


def test_field_invariant_must_hold():
    with pytest.raises(InvariantException):
        Point(x=-1)


def test_initial_value_set_when_not_present_in_arguments():
    p = Point(x=1, y=2)

    assert p.z == 0


class Line(PClass):
    p1 = field(type=Point)
    p2 = field(type=Point)


def test_can_create_nested_structures_from_dict_and_serialize_back_to_dict():
    source = dict(p1=dict(x=1, y=2, z=3), p2=dict(x=10, y=20, z=30))
    l = Line.create(source)

    assert l.p1.x == 1
    assert l.p1.y == 2
    assert l.p1.z == 3
    assert l.p2.x == 10
    assert l.p2.y == 20
    assert l.p2.z == 30

    assert l.serialize(format=lambda val: val) == source


def test_can_serialize_with_custom_serializer():
    p = Point(x=1, y=1, z=1)

    assert p.serialize(format=lambda v: v + 17) == {'x': 1, 'y': 18, 'z': 1}


def test_implements_proper_equality_based_on_equality_of_fields():
    p1 = Point(x=1, y=2)
    p2 = Point(x=3)
    p3 = Point(x=1, y=2)

    assert p1 == p3
    assert not p1 != p3
    assert p1 != p2
    assert not p1 == p2


def test_is_hashable():
    p1 = Point(x=1, y=2)
    p2 = Point(x=3, y=2)

    d = {p1: 'A point', p2: 'Another point'}

    p1_like = Point(x=1, y=2)
    p2_like = Point(x=3, y=2)

    assert isinstance(p1, Hashable)
    assert d[p1_like] == 'A point'
    assert d[p2_like] == 'Another point'
    assert Point(x=10) not in d


def test_supports_nested_transformation():
    l1 = Line(p1=Point(x=2, y=1), p2=Point(x=20, y=10))

    l2 = l1.transform(['p1', 'x'], 3)

    assert l1.p1.x == 2

    assert l2.p1.x == 3
    assert l2.p1.y == 1
    assert l2.p2.x == 20
    assert l2.p2.y == 10


def test_repr():
    l = Line(p1=Point(x=2, y=1), p2=Point(x=20, y=10))

    assert repr(l) == 'Line(p2=Point(y=10, x=20, z=0), p1=Point(y=1, x=2, z=0))'


def test_global_invariant_check():
    class UnitCirclePoint(PClass):
        __invariant__ = lambda cp: (0.99 < math.sqrt(cp.x*cp.x + cp.y*cp.y) < 1.01,
                                    "Point not on unit circle")
        x = field(type=float)
        y = field(type=float)

    UnitCirclePoint(x=1.0, y=0.0)

    with pytest.raises(InvariantException):
        UnitCirclePoint(x=1.0, y=1.0)


def test_supports_pickling():
    p1 = Point(x=2, y=1)
    p2 = pickle.loads(pickle.dumps(p1, -1))

    assert p1 == p2
    assert isinstance(p2, Point)


def test_can_remove_optional_member():
    p1 = Point(x=1, y=2)
    p2 = p1.remove('y')

    assert p2 == Point(x=1)


def test_cannot_remove_mandatory_member():
    p1 = Point(x=1, y=2)

    with pytest.raises(InvariantException):
        p1.remove('x')


def test_cannot_remove_non_existing_member():
    p1 = Point(x=1)

    with pytest.raises(AttributeError):
        p1.remove('y')
