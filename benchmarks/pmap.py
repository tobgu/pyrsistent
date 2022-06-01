from pyperform import BenchmarkedFunction
from pyrsistent import pmap #!


class Benchmarked(BenchmarkedFunction):
    def __init__(self, scale=1, *args, **kwargs):
        super(Benchmarked, self).__init__(*args, timeit_number=scale*1000, **kwargs)

################# Create ###################

@Benchmarked()
def create_empty_pmap():
    for x in range(1000):
        _ = pmap()

@Benchmarked()
def reference_create_empty_dict():
    for x in range(1000):
        _ = dict()


def _small_dict():
    small_dict = dict((i, i) for i in range(10))


def _large_dict():
    large_dict = dict((i, i) for i in range(2000))


@Benchmarked(setup=_small_dict)
def create_small_pmap():
    for x in range(100):
        _ = pmap(small_dict)


@Benchmarked(setup=_small_dict)
def reference_create_small_dict():
    for x in range(100):
        _ = dict(small_dict)


@Benchmarked(setup=_large_dict)
def create_large_pmap():
    for x in range(1):
        _ = pmap(large_dict)


@Benchmarked(setup=_large_dict)
def reference_create_large_dict():
    for x in range(1):
        _ = dict(large_dict)


# ######################### Insert ######################


def _small_pmap():
    small_pmap = pmap(dict((i, i) for i in range(10)))


@Benchmarked(setup=_small_pmap)
def random_replace_small_pmap():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        small_pmap.set(x, x)


@Benchmarked(setup=_small_dict)
def reference_random_replace_small_dict():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        small_dict[x] = x


def _large_pmap():
    large_pmap = pmap(dict((i, i) for i in range(2000)))


@Benchmarked(setup=_large_pmap)
def random_replace_large_pmap():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        large_pmap.set(x, x)


@Benchmarked(setup=_large_dict)
def reference_random_replace_large_dict():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        large_dict[x] = x


@Benchmarked(setup=_small_pmap)
def random_replace_small_pmap_evolver():
    e = small_pmap.evolver()
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        e[x] = x
    m = e.persistent()


@Benchmarked(setup=_large_pmap)
def random_replace_large_pmap_evolver():
    e = large_pmap.evolver()
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        e[x] = x
    m = e.persistent()


@Benchmarked(setup=_small_pmap)
def random_insert_new_small_pmap():
    for x in (19, 11, 14, 15, 17, 117, 13, 12):
        small_pmap.set(x, x)


@Benchmarked(setup=_small_dict)
def reference_random_insert_new_small_dict():
    for x in (19, 11, 14, 15, 17, 117, 13, 12):
        small_dict[x] = x


@Benchmarked(setup=_large_pmap)
def random_insert_new_large_pmap():
    for x in (100999, 100111, 10074, 1001233, 1006, 1001997, 100400, 1001000):
        large_pmap.set(x, x)


@Benchmarked(setup=_large_dict)
def reference_random_insert_new_large_dict():
    for x in (100999, 100111, 10074, 1001233, 1006, 1001997, 100400, 1001000):
        large_dict[x] = x


# ################## Read ########################

@Benchmarked(setup=_small_pmap)
def random_read_small_pmap():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        y = small_pmap[x]


@Benchmarked(setup=_small_dict)
def reference_random_read_small_dict():
    for x in (9, 1, 4, 5, 7, 7, 3, 2):
        y = small_dict[x]


@Benchmarked(setup=_large_pmap)
def random_read_large_native_pvector():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        y = large_pmap[x]


@Benchmarked(setup=_large_dict)
def reference_random_read_large_list():
    for x in (999, 111, 74, 1233, 6, 1997, 400, 1000):
        y = large_dict[x]


# #################### Iteration #########################

@Benchmarked(setup=_large_pmap)
def iteration_large_pmap():
    for k in large_pmap:
        pass


@Benchmarked(setup=_large_dict)
def reference_iteration_large_dict():
    for k in large_dict:
        pass


# #################### Comparison ########################

def _different_pmaps_same_size():
    pmap1 = pmap(dict((i, i) for i in range(2000)))
    pmap2 = pmap(dict((i, i + 1) for i in range(2000)))


def _different_pmaps_different_size():
    pmap1 = pmap(dict((i, i) for i in range(2000)))
    pmap2 = pmap(dict((i, i + 1) for i in range(1500)))


def _equal_pmaps():
    pmap1 = pmap(dict((i, i) for i in range(2000)))
    pmap2 = pmap(dict((i, i) for i in range(2000)))


def _equal_pmap_and_dict():
    dict1 = dict((i, i) for i in range(2000))
    pmap1 = pmap(dict((i, i) for i in range(2000)))


def _equal_dicts():
    dict1 = dict((i, i) for i in range(2000))
    dict2 = dict((i, i) for i in range(2000))


def _different_dicts_same_size():
    dict1 = dict((i, i) for i in range(2000))
    dict2 = dict((i, i + 1) for i in range(2000))


def _different_dicts_different_size():
    dict1 = dict((i, i) for i in range(2000))
    dict2 = dict((i, i + 1) for i in range(2000))


def _equal_pmaps_different_bucket_size():
    pmap1 = pmap(dict((i, i) for i in range(2000)), 1999)
    pmap2 = pmap(dict((i, i) for i in range(2000)), 2000)


def _equal_pmaps_same_bucket_size_different_insertion_order():
    pmap1 = pmap([(i, i) for i in range(2000)], 1999)
    pmap2 = pmap([(i, i) for i in range(1999, -1, -1)], 1999)


@Benchmarked(setup=_large_pmap)
def compare_same_pmap():
    large_pmap == large_pmap


@Benchmarked(setup=_large_dict)
def reference_compare_same_dict():
    large_dict == large_dict


@Benchmarked(setup=_equal_pmaps)
def compare_equal_pmaps():
    pmap1 == pmap2


@Benchmarked(setup=_equal_dicts)
def reference_compare_equal_dicts():
    dict1 == dict2


@Benchmarked(setup=_equal_pmap_and_dict)
def compare_equal_pmap_and_dict():
    pmap1 == dict1


@Benchmarked(setup=_equal_pmaps_same_bucket_size_different_insertion_order)
def compare_equal_pmaps_different_insertion_order():
    pmap1 == pmap2


@Benchmarked(setup=_equal_pmaps_different_bucket_size)
def compare_equal_pmaps_different_bucket_size():
    pmap1 == pmap2


@Benchmarked(setup=_different_pmaps_same_size)
def compare_different_pmaps_same_size():
    pmap1 == pmap2


@Benchmarked(setup=_different_dicts_same_size)
def reference_compare_different_dicts_same_size():
    dict1 == dict2


@Benchmarked(setup=_different_pmaps_different_size)
def compare_different_pmaps_different_size():
    pmap1 == pmap2


@Benchmarked(setup=_different_dicts_different_size)
def reference_compare_different_dicts_different_size():
    dict1 == dict2
