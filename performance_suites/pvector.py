from pyperform import BenchmarkedFunction
from pyrsistent import _pvector, _pvector #!


class Benchmarked(BenchmarkedFunction):
    def __init__(self, scale=1, *args, **kwargs):
        super(Benchmarked, self).__init__(*args, timeit_number=scale*1000, **kwargs)

################# Create ###################

@Benchmarked()
def create_empty_native_pvector():
    for x in range(1000):
        _ = _pvector()

@Benchmarked()
def create_empty_python_pvector():
    for x in range(1000):
        _ = _pvector()

@Benchmarked()
def reference_create_empty_list():
    for x in range(1000):
        _ = list()

def _small_list():
    small_list = range(10)

def _large_list():
    large_list = range(2000)

@Benchmarked(setup=_small_list)
def create_small_native_pvector():
    for x in range(100):
        _ = _pvector(small_list)

@Benchmarked(setup=_small_list)
def create_small_python_pvector():
    for x in range(100):
        _ = _pvector(small_list)

@Benchmarked(setup=_small_list)
def reference_create_small_list():
    for x in range(100):
        _ = list(small_list)

@Benchmarked(setup=_large_list)
def create_large_native_pvector():
    for x in range(10):
        _ = _pvector(large_list)

@Benchmarked(setup=_large_list)
def create_large_python_pvector():
    for x in range(10):
        _ = _pvector(large_list)

@Benchmarked(setup=_large_list)
def reference_create_large_list():
    for x in range(10):
        _ = list(large_list)


####################### Append #####################

@Benchmarked()
def append_native_pvector():
    v = _pvector()
    for x in range(100):
        v = v.append(x)

@Benchmarked()
def append_python_pvector():
    v = _pvector()
    for x in range(100):
        v = v.append(x)

@Benchmarked()
def reference_append_list():
    l = []
    for x in range(100):
        l.append(x)

@Benchmarked()
def append_native_pvector():
    v = _pvector()
    for x in range(100):
        v = v.append(x)

@Benchmarked()
def append_python_pvector():
    v = _pvector()
    for x in range(100):
        v = v.append(x)

@Benchmarked()
def reference_append_list():
    l = []
    for x in range(100):
        l.append(x)


######################### Insert ######################

def _small_native_vector():
    small_native_vector = _pvector(range(10))


def _small_python_vector():
    small_python_vector = _pvector(range(10))


@Benchmarked(setup=_small_native_vector)
def random_insert_small_native_pvector():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        small_native_vector.set(x, x)


@Benchmarked(setup=_small_python_vector)
def random_insert_small_python_pvector():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        small_python_vector.set(x, x)


@Benchmarked(setup=_small_list)
def reference_random_insert_small_list():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        small_list[x] = x


def _large_native_vector():
    large_native_vector = _pvector(range(2000))


def _large_python_vector():
    large_python_vector = _pvector(range(2000))


@Benchmarked(setup=_large_native_vector)
def random_insert_large_native_pvector():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        large_native_vector.set(x, x)


@Benchmarked(setup=_large_python_vector)
def random_insert_large_python_pvector():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        large_python_vector.set(x, x)


@Benchmarked(setup=_large_list)
def reference_random_insert_large_list():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        large_list[x] = x


@Benchmarked(setup=_small_native_vector)
def random_insert_small_native_pvector_evolver():
    e = small_native_vector.evolver()
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        e[x] = x
    v = e.persistent()


@Benchmarked(setup=_small_python_vector)
def random_insert_small_python_pvector_evolver():
    e = small_python_vector.evolver()
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        e[x] = x
    v = e.persistent()


@Benchmarked(setup=_large_native_vector)
def random_insert_large_native_pvector_evolver():
    e = large_native_vector.evolver()
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        e[x] = x
    v = e.persistent()


@Benchmarked(setup=_large_python_vector)
def random_insert_large_native_pvector_evolver():
    e = large_python_vector.evolver()
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        e[x] = x
    v = e.persistent()

################## Read ########################

@Benchmarked(setup=_small_native_vector)
def random_read_small_native_pvector():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        y = small_native_vector[x]


@Benchmarked(setup=_small_python_vector)
def random_read_small_python_pvector():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        y = small_python_vector[x]


@Benchmarked(setup=_small_list)
def reference_random_read_small_list():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        y = small_list[x]


@Benchmarked(setup=_large_native_vector)
def random_read_large_native_pvector():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        y = large_native_vector[x]


@Benchmarked(setup=_large_python_vector)
def random_read_large_python_pvector():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        y = large_python_vector[x]


@Benchmarked(setup=_large_list)
def reference_random_read_large_list():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        y = large_list[x]


#################### Iteration #########################

@Benchmarked(setup=_large_native_vector)
def iteration_large_native_pvector():
    for x in large_native_vector:
        pass

@Benchmarked(setup=_large_python_vector)
def iteration_large_python_pvector():
    for x in large_python_vector:
        pass

@Benchmarked(setup=_large_list)
def reference_iteration_large_list():
    for x in large_list:
        pass