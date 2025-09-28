from enum import Enum

from pyrsistent import field, pvector_field


class ExampleEnum(Enum):
    x = 1
    y = 2


def test_enum():
    f = field(type=ExampleEnum)

    assert ExampleEnum in f.type  # type: ignore[reportGeneralTypeIssues]
    assert len(f.type) == 1  # type: ignore[reportGeneralTypeIssues]


# This is meant to exercise `_seq_field`.
def test_pvector_field_enum_type():
    f = pvector_field(ExampleEnum)

    assert len(f.type) == 1  # type: ignore[reportGeneralTypeIssues]
    assert ExampleEnum is list(f.type)[0].__type__  # type: ignore[reportGeneralTypeIssues]
