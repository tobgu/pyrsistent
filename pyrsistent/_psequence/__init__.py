from collections.abc import Sequence, Hashable, MutableSequence
import os

_use_c_ext = False
# Use the C extension as underlying implementation if it is available
if not os.environ.get('PYRSISTENT_NO_C_EXTENSION'): # pragma: no cover
    try:
        from pyrsistent._psequence._c_ext import psequence, PSequence, Evolver
        _use_c_ext = True
    except ImportError as err:
        pass

if not _use_c_ext:
    from pyrsistent._psequence._python import psequence, PSequence, Evolver

Sequence.register(PSequence)
Hashable.register(PSequence)
MutableSequence.register(Evolver)

def sq(*elements):
    return psequence(elements)

__all__ = ('psequence', 'PSequence', 'sq')
