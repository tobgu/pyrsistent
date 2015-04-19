import pytest
from pyrsistent import field, InvariantException
from pyrsistent import PClass


class Point(PClass):
    x = field(type=int, mandatory=True, invariant=lambda x: (x >= 0, 'X negative'))
    y = field(type=int)


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
        Point(x=1, z=5)


def test_cannot_construct_with_wrong_type():
    with pytest.raises(TypeError):
        Point(x='a')


def test_cannot_construct_without_mandatory_fields():
    with pytest.raises(InvariantException):
        Point(y=1)


def test_field_invariant_must_hold():
    with pytest.raises(InvariantException):
        Point(x=-1)

# Test list:
# - Initial/default (make possible to be a lambda if this is not already the case)
# - Nested construction with other checked types
# - Global invariant checks
# - Serialization and creation
# - Repr
# - Evolver
# - Transformation
# - Inheritance
# - Pickling
# - Without/del to remove a member?
# - Do we want it to be possible to monkey patch by evolution?
# - Hash and equality

# TODO
# - File with shared functions and field handling
# - Rename PRecordTypeError and move to common file
# - Difference in when the type error is raised in the PClass and the PRecord right now
