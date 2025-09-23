# Check that the inferred types are as expected.

from typing_extensions import assert_type
from pyrsistent import PMap, pmap

assert_type(pmap(dict[tuple[int, str], float]()), PMap[tuple[int, str], float])
