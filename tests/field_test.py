from pyrsistent import field


def test_enum():
    try:
        from enum import Enum
    except ImportError:
        # skip enum test if Enums are not available
        return

    class TestEnum(Enum):
        x = 1
        y = 2

    f = field(type=TestEnum)

    assert TestEnum in f.type
    assert len(f.type) == 1
