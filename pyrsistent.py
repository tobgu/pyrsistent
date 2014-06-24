"""
A very thin facade containing all factory functions and hiding the actual implementation used.
"""
from pyrsistent_types import pvector as pvector_python, pmap as pmap_python, pset as pset_python

pvector = pvector_python

try:
    from pvectorc import pvector as pvector_c
    pvector = pvector_c
except:
    pass

def v(*elements):
    """
    Factory function, returns a new PVector object containing all parameters.
    """
    return pvector(elements)


pmap = pmap_python

def m(**kwargs):
    """
    Factory function, inserts all key value arguments into the newly created map.
    """
    return pmap(kwargs)

pset = pset_python

def s(*args):
    return pset(args)
