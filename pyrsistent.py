from collections import Sequence, Mapping, Set
from itertools import chain


def bitcount(val):
    return bin(val).count("1")


BRANCH_FACTOR = 32
BIT_MASK = BRANCH_FACTOR - 1
SHIFT = bitcount(BIT_MASK)

class PVector(Sequence):
    """
    Persistent vector, persistent in the sense that it is immutable (if only accessing the public API)

    Heavily influenced by the persistent data structures available in Clojure. Initially this was more or
    less just a port of the Java code for the Clojure data structures. It has since been modified and to
    some extent optimized for usage in Python.

    The vector is organized as a trie, any mutating method will return a new vector that contains the changes. No
    updates are done to the original vector. Structural sharing between vectors are applied where possible to save
    space and to avoid making complete copies.

    Performance is generally in the range of 2 - 100 times slower than using the built in mutable list type in Python.
    It may be better in some cases and worse in others. Fully PyPy compatible, running it under PyPy speeds operations
    up considerably if the structure is used heavily (if JITed).
    """
    def __init__(self, c, s, r, t):
        """
        Should never be created directly, use the pvector() / pvec() factory function instead.
        """
        self._count = c
        self._shift = s
        self._root = r
        self._tail = t
        self._tail_offset = self._count - len(self._tail)

    def __len__(self):
        return self._count

    def __getitem__(self, index):
        if isinstance(index, slice):
            # This is a bit nasty realizing the whole structure as a list before
            # slicing it but it is the fastest way I've found to date, and it's easy :-)
            return pvector(self.tolist()[index])

        return self._list_for(index)[index & BIT_MASK]

    def __add__(self, other):
        return self.extend(other)

    def __str__(self):
        return str(self.tolist())

    def __iter__(self):
        # This is kind of lazy and will produce some memory overhead but it is the fasted method
        # by far of those tried since it uses the speed of the built in python list directly.
        return iter(self.tolist())

    def tostr(self):
        return str(self.tolist())

    def _fill_list(self, node, shift, the_list):
        if shift:
            shift -= SHIFT
            for n in node:
                self._fill_list(n, shift, the_list)
        else:
            the_list.extend(node)

    def tolist(self):
        the_list = []
        self._fill_list(self._root, self._shift, the_list)
        the_list.extend(self._tail)
        return the_list

    def totuple(self):
        return tuple(self.tolist())

    def assoc(self, i, val):
        if 0 <= i < self._count:
            if i >= self._tail_offset:
                new_tail = list(self._tail)
                new_tail[i & BIT_MASK] = val
                return PVector(self._count, self._shift, self._root, new_tail)

            return PVector(self._count, self._shift, self._do_assoc(self._shift, self._root, i, val), self._tail)

        if i == self._count:
            return self.append(val)

        raise IndexError()

    def _do_assoc(self, level, node, i, val):
        ret = list(node)
        if level == 0:
            ret[i & BIT_MASK] = val
        else:
            sub_index = (i >> level) & BIT_MASK  # >>>
            ret[sub_index] = self._do_assoc(level - SHIFT, node[sub_index], i, val)

        return ret

    def _list_for(self, i):
        if 0 <= i < self._count:

            if i >= self._tail_offset:
                return self._tail

            node = self._root
            for level in range(self._shift, 0, -SHIFT):
                node = node[(i >> level) & BIT_MASK]  # >>>

            return node

        raise IndexError()

    def _create_new_root(self):
        new_shift = self._shift

        # Overflow root?
        if (self._count >> SHIFT) > (1 << self._shift): # >>>
            new_root = [self._root, self._new_path(self._shift, self._tail)]
            new_shift += SHIFT
        else:
            new_root = self._push_tail(self._shift, self._root, self._tail)

        return new_root, new_shift

    def append(self, val):
        if len(self._tail) < BRANCH_FACTOR:
            new_tail = list(self._tail)
            new_tail.append(val)
            return PVector(self._count + 1, self._shift, self._root, new_tail)

        # Full tail, push into tree
        new_root, new_shift = self._create_new_root()
        return PVector(self._count + 1, new_shift, new_root, [val])

    def _new_path(self, level, node):
        if level == 0:
            return node

        return [self._new_path(level - SHIFT, node)]

    def _mutating_insert_tail(self):
        self._root, self._shift = self._create_new_root()
        self._tail = []

    def _mutating_fill_tail(self, offset, sequence):
        max_delta_len = BRANCH_FACTOR - len(self._tail)
        delta = sequence[offset:offset + max_delta_len]
        self._tail.extend(delta)
        delta_len = len(delta)
        self._count += delta_len
        return offset + delta_len

    def _mutating_extend(self, sequence):
        offset = 0
        sequence_len = len(sequence)
        while offset < sequence_len:
            offset = self._mutating_fill_tail(offset, sequence)
            if len(self._tail) == BRANCH_FACTOR:
                self._mutating_insert_tail()

        self._tail_offset = self._count - len(self._tail)

    def extend(self, obj):
        # Mutates the new vector directly for efficiency but that's only an
        # implementation detail, once it is returned it should be considered immutable
        l = obj.tolist() if isinstance(obj, PVector) else list(obj)
        if l:
            new_vector = self.append(l[0])
            new_vector._mutating_extend(l[1:])
            return new_vector

        return self

    def _push_tail(self, level, parent, tail_node):
        """
        if parent is leaf, insert node,
        else does it map to an existing child? ->
             node_to_insert = push node one more level
        else alloc new path

        return  node_to_insert placed in copy of parent
        """
        ret = list(parent)

        if level == SHIFT:
            ret.append(tail_node)
            return ret

        sub_index = ((self._count - 1) >> level) & BIT_MASK  # >>>
        if len(parent) > sub_index:
            ret[sub_index] = self._push_tail(level - SHIFT, parent[sub_index], tail_node)
            return ret

        ret.append(self._new_path(level - SHIFT, tail_node))
        return ret


_EMPTY_VECTOR = PVector(0, SHIFT, [], [])


def pvector(elements=[]):
    vec = _EMPTY_VECTOR
    return vec.extend(elements)


def pvec(*elements):
    return pvector(elements)

####################### PMap #####################################


class PMap(Mapping):
    def __init__(self, size, buckets):
        self._size = size
        self._buckets = buckets

    def _get_bucket(self, key):
        h = hash(key)
        index = h % len(self._buckets)
        bucket = self._buckets[index]
        return index, bucket

    def __getitem__(self, key):
        _, bucket = self._get_bucket(key)
        if bucket:
            for k, v in bucket:
                if k == key:
                    return v

        raise KeyError

    def __iter__(self):
        return self.iterkeys()

    def __getattr__(self, key):
        return self[key]

    def iterkeys(self):
        for k, _ in self.iteritems():
            yield k

    # These are more efficient implementations compared to the original
    # methods that is based on the keys iterator and then calls the
    # accessor functions to access the value for the corresponding key
    def itervalues(self):
        for _, v in self.iteritems():
            yield v

    def iteritems(self):
        for bucket in self._buckets:
            if bucket:
                for k, v in bucket:
                    yield k, v

    def values(self):
        return list(self.itervalues())

    def keys(self):
        return list(self.iterkeys())

    def items(self):
        return list(self.iteritems())

    def __len__(self):
        return self._size

    def __str__(self):
        return str(self.todict())

    def todict(self):
        return dict(self.iteritems())

    def assoc(self, key, val):
        kv = (key, val)
        index, bucket = self._get_bucket(key)
        if bucket:
            for k, v in bucket:
                if k == key:
                    if v is val:
                        return self
                    else:
                        new_bucket = [(k2, v2) if k2 != k else (k2, val) for k2, v2 in bucket]
                        return PMap(self._size, self._buckets.assoc(index, new_bucket))

            if len(self._buckets) < 0.67 * self._size:
                return PMap(self._size, self._reallocate(2 * len(self._buckets))).assoc(key, val)
            else:
                new_bucket = [kv]
                new_bucket.extend(bucket)
                new_buckets = self._buckets.assoc(index, new_bucket)

            return PMap(self._size + 1, new_buckets)

        # Skip reallocation check if there was no conflict
        return PMap(self._size + 1, self._buckets.assoc(index, [kv]))

    def without(self, key):
        # Should shrinking of the map ever be done if it becomes very small?
        index, bucket = self._get_bucket(key)

        if bucket:
            new_bucket = [(k, v) for (k, v) in bucket if k != key]
            if len(bucket) > len(new_bucket):
                return PMap(self._size - 1, self._buckets.assoc(index, new_bucket if new_bucket else None))

        return self

    def _reallocate_to_list(self, new_size):
        new_list = new_size * [None]
        new_len = len(new_list)
        for k, v in chain.from_iterable(x for x in self._buckets if x):
            index = hash(k) % new_len
            if new_list[index]:
                new_list[index].append((k, v))
            else:
                new_list[index] = [(k, v)]

        return new_list

    def _reallocate(self, new_size):
        return pvector(self._reallocate_to_list(new_size))


def pmap(**kwargs):
    return pmapping(kwargs)


def _turbo_mapping(initial, pre_size):
    size = pre_size or (2 * len(initial)) or 8
    buckets = size * [None]

    if not isinstance(initial, Mapping):
        # Make a dictionary of the initial data if it isn't already,
        # that will save us some job further down since we can assume no
        # key collisions
        initial = dict(initial)

    for k, v in initial.iteritems():
        h = hash(k)
        index = h % size
        bucket = buckets[index]

        if bucket:
            bucket.append((k, v))
        else:
            buckets[index] = [(k, v)]

    return PMap(len(initial), pvector(buckets))


def pmapping(initial={}, pre_size=0):
    return _turbo_mapping(initial, pre_size)


##################### Pset ########################

class PSet(Set):
    def __init__(self, m):
        self._map = m

    def __contains__(self, element):
        return element in self._map

    def __iter__(self):
        return iter(self._map)

    def __len__(self):
        return len(self._map)

    def __str__(self):
        return str(self.toset())

    def toset(self):
        return set(iter(self))

    @classmethod
    def _from_iterable(cls, it, pre_size=8):
        return PSet(pmapping({k: True for k in it}, pre_size=pre_size))

    def toset(self):
        return set(self._map)

    def add(self, element):
        return PSet(self._map.assoc(element, True))

    def without(self, element):
        return PSet(self._map.without(element))


def pset(elements=[], pre_size=0):
    return PSet._from_iterable(elements, pre_size=pre_size)