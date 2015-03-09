from pyperform import BenchmarkedFunction
from pyrsistent import pvector, _pvector #!

@BenchmarkedFunction(setup=None, timeit_repeat=3, timeit_number=1000)
def create_empty_native_pvector():
    for x in range(1000):
        _ = pvector()

@BenchmarkedFunction(setup=None, timeit_repeat=3, timeit_number=1000)
def create_empty_python_pvector():
    for x in range(1000):
        _ = _pvector()