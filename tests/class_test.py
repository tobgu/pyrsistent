import pytest
from pyrsistent import field
from pyrsistent._pclass import PClass


class Point(PClass):
    x = field(type=int)
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


def test_direct_assignment_not_possible():
    with pytest.raises(AttributeError):
        Point(x=1, y=2).x = 1


def test_direct_delete_not_possible():
    with pytest.raises(AttributeError):
        del Point(x=1, y=2).x


def test_cannot_construct_with_undeclared_fields():
    with pytest.raises(AttributeError):
        Point(z=5)


# Test list:
# - set() using *args
# - Type checks
# - Initial/default (make possible to be a lambda if this is not already the case)
# - Invariant checks, global and local
# - Serialization and creation
# - Repr
# - Evolver
# - Transformation
# - Inheritance
# - Pickling
# - Without/del to remove a member?
# - Do we want it to be possible to monkey patch by evolution?