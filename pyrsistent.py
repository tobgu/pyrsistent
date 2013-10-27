from collections import Sequence, Mapping, Set
from itertools import chain


def bitcount(val):
    return bin(val).count("1")


BRANCH_FACTOR = 32
BIT_MASK = BRANCH_FACTOR - 1
SHIFT = bitcount(BIT_MASK)


class PVector(Sequence):
    """
    Persistant vector, persistant in the sense that it is immutable (if only accessing the public API)

    Heavily influenced by the persistant data structures available in Clojure. Initially this was more or
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
        # TODO: Calculate tail offset?

    def __len__(self):
        return self._count

    def __getitem__(self, index):
        if isinstance(index, slice):
            # This is a bit nasty realizing the whole structure as a list before
            # slicing it but it is the fastest way I've found to date
            return pvector(self.tolist()[index])

        return self._list_for(index)[index & BIT_MASK]

    def __add__(self, other):
        return self.extend(other)

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

    def assoc(self, i, val):
        if 0 <= i < self._count:
            if i >= self._tail_offset():
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

    # TODO: Consider rewriting this to remove the function call and calculate the tail offset once
    #       to avoid overhead when accessing elements in the vector
    def _tail_offset(self):
        return self._count - len(self._tail)

    def _list_for(self, i):
        if 0 <= i < self._count:

            if i >= self._tail_offset():
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

        # TODO: Set the tail offset here...

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


def empty_list(length):
    return [None] * length


class Box(object):
    def __init__(self, val=None):
        self.val = val


def mask(hash, shift):
    return (hash >> shift) & BIT_MASK # >>>


def bitpos(hash, shift):
    return 1 << mask(hash, shift)


def remove_pair(array, index):
    return array[:2 * index] + array[2 * (index + 1):]


class HashCollisionNode(object):
    def __init__(self, hash, array):
        self.hash = hash
        self.array = array

    def find_index(self, key):
        for i in range(0, 2 * self.count(), 2):
            if key == self.array[i]:
                return i
        return -1

    def __iter__(self):
        for i in range(0, 2 * self.count(), 2):
            yield (self.array[i], self.array[i + 1])

    def assoc(self, shift, key, val, added_leaf):
        the_hash = hash(key)
        if the_hash == self.hash:
            idx = self.find_index(key)
            if idx != -1:
                if self.array[idx + 1] is val:
                    return self

                # Copy with new value
                return HashCollisionNode(self.hash, clone_and_set(self.array, idx + 1, val))

            # Create a copy of us with size + 2 to hold the new element
            new_array = list(self.array)
            new_array.append(key)
            new_array.append(val)
            added_leaf.val = added_leaf
            return HashCollisionNode(the_hash, new_array)

        # Another hash, nest ourselves in a bitmap indexed node
        return BitmapIndexedNode(bitpos(self.hash, shift), [None, self]).assoc(shift, key, val, added_leaf)

    def find(self, shift, key):
        # Shift parameter not used here but must exist to adhere to Node protocol
        idx = self.find_index(key)
        if idx < 0:
            raise KeyError

        return self.array[idx + 1]

    def count(self):
        return len(self.array) / 2

    def without(self, shift, key):
        # Shift parameter not used here but must exist to adhere to Node protocol
        idx = self.find_index(key)
        if idx == -1:
            return self

        if self.count() == 1:
            return None

        return HashCollisionNode(self.hash, remove_pair(self.array, idx / 2))


def create_node(shift, key1, val1, key2, val2):
    key1hash = hash(key1)
    key2hash = hash(key2)
    if key1hash == key2hash:
        return HashCollisionNode(key1hash, [key1, val1, key2, val2])

    _ = Box()
    return BitmapIndexedNode.EMPTY \
        .assoc(shift, key1, val1, _) \
        .assoc(shift, key2, val2, _)


def clone_and_set(original, index, value):
    clone = list(original)
    clone[index] = value
    return clone


def clone_and_set2(original, index1, value1, index2, value2):
    clone = list(original)
    clone[index1] = value1
    clone[index2] = value2
    return clone


class ArrayNode(object):
    def __iter__(self):
        for node in self.array:
            if node:
                for k, v in node:
                    yield (k, v)

    def __init__(self, count, array):
        self.array = array
        self.count = count

    def assoc(self, shift, key, val, added_leaf):
        hash_value = hash(key)
        idx = mask(hash_value, shift)
        node = self.array[idx]

        if node is None:
            return ArrayNode(self.count + 1,
                             clone_and_set(self.array, idx,
                                           BitmapIndexedNode.EMPTY.assoc(shift + SHIFT, key, val, added_leaf)))

        n = node.assoc(shift + SHIFT, key, val, added_leaf)
        if n is node:
            return self

        return ArrayNode(self.count, clone_and_set(self.array, idx, n))

    def find(self, shift, key):
        hash_value = hash(key)
        idx = mask(hash_value, shift)
        node = self.array[idx]
        if node is None:
            raise KeyError

        return node.find(shift + SHIFT, key)

    def without(self, shift, key):
        key_hash = hash(key)
        idx = mask(key_hash, shift)
        node = self.array[idx]
        if node is None:
            return self

        n = node.without(shift + SHIFT, key)
        if n is node:
            return self
        elif n is None:
            # TODO: Removed packing optimization if size <= 8 here temporarily...
            return ArrayNode(self.count - 1, clone_and_set(self.array, idx, n))
        else:
            return ArrayNode(self.count, clone_and_set(self.array, idx, n))


class BitmapIndexedNode(object):
    def __iter__(self):
        for i in xrange(0, len(self.array), 2):
            key_or_none = self.array[i]
            val_or_node = self.array[i + 1]
            if key_or_none is None:
                for k, v in val_or_node:
                    yield (k, v)
            else:
                yield (key_or_none, val_or_node)

    def __init__(self, bitmap, array):
        self.bitmap = bitmap
        self.array = array

    def index(self, bit):
        return bitcount(self.bitmap & (bit - 1))

    def assoc(self, shift, key, val, added_leaf):
        hash_value = hash(key)
        bit = bitpos(hash_value, shift)

        idx = self.index(bit)
        if self.bitmap & bit:
            # Value with the same partial hash value already exists
            key_or_none = self.array[2 * idx]
            val_or_node = self.array[2 * idx + 1]
            if key_or_none is None:
                # Node
                node = val_or_node.assoc(shift + SHIFT, key, val, added_leaf)
                if node is val_or_node:
                    return self
                return BitmapIndexedNode(self.bitmap, clone_and_set(self.array, 2 * idx + 1, node))

            if key == key_or_none:
                # BitmapIndexedNode, replace existing value
                if val is val_or_node:
                    return self
                return BitmapIndexedNode(self.bitmap, clone_and_set(self.array, 2 * idx + 1, val))

            # BitmapIndexedNode, add new value
            added_leaf.val = added_leaf
            return BitmapIndexedNode(self.bitmap,
                                     clone_and_set2(self.array,
                                                    2 * idx, None,
                                                    2 * idx + 1,
                                                    create_node(shift + SHIFT, key_or_none, val_or_node, key, val)))
        else:
            # Unique hash_value value
            n = bitcount(self.bitmap)
            if n >= (BRANCH_FACTOR / 2):
                # This node is full. Need to convert it into an ArrayNode.
                nodes = empty_list(BRANCH_FACTOR)
                jdx = mask(hash_value, shift)
                nodes[jdx] = BitmapIndexedNode.EMPTY.assoc(shift + SHIFT, key, val, added_leaf)
                # Copy all values
                j = 0
                for i in range(BRANCH_FACTOR):
                    if (self.bitmap >> i) & 1: # >>>
                        if self.array[j] is None:
                            # Sub node
                            nodes[i] = self.array[j + 1]
                        else:
                            # key - value pair
                            nodes[i] = BitmapIndexedNode.EMPTY.assoc(shift + SHIFT, self.array[j], self.array[j + 1],
                                                                     added_leaf)
                        j += 2
                return ArrayNode(n + 1, nodes)
            else:
                new_array = self.array[:2 * idx]
                new_array.append(key)
                new_array.append(val)
                added_leaf.val = added_leaf
                new_array.extend(self.array[2 * idx:])
                return BitmapIndexedNode(self.bitmap | bit, new_array)

    def find(self, shift, key):
        bit = bitpos(hash(key), shift)
        if (self.bitmap & bit) == 0:
            raise KeyError

        idx = self.index(bit)
        key_or_none = self.array[2 * idx]
        val_or_node = self.array[2 * idx + 1]
        if key_or_none is None:
            return val_or_node.find(shift + SHIFT, key)

        if key == key_or_none:
            return val_or_node

        raise KeyError

    def without(self, shift, key):
        the_hash = hash(key)
        bit = bitpos(the_hash, shift)

        if (self.bitmap & bit) == 0:
            return self

        idx = self.index(bit)
        key_or_none = self.array[2 * idx]
        val_or_node = self.array[2 * idx + 1]
        if key_or_none is None:
            n = val_or_node.without(shift + SHIFT, key)
            if n == val_or_node:
                return self
            if n is not None:
                return BitmapIndexedNode(self.bitmap, clone_and_set(self.array, 2 * idx + 1, n))
            if self.bitmap == bit:
                # Last value in this node
                return None
            return BitmapIndexedNode(self.bitmap ^ bit, remove_pair(self.array, idx))

        if key == key_or_none:
            # TODO: collapse
            return BitmapIndexedNode(self.bitmap ^ bit, remove_pair(self.array, idx))

        return self


BitmapIndexedNode.EMPTY = BitmapIndexedNode(0, [])


class PMap(Mapping):
    def __init__(self, count, root):
        self.count = count
        self.root = root

    def __getitem__(self, key):
        if self.root:
            return self.root.find(0, key)

        raise KeyError

    def __iter__(self):
        return self.iterkeys()

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
        return iter(self.root if self.root else [])

    def values(self):
        return list(self.itervalues())

    def keys(self):
        return list(self.iterkeys())

    def items(self):
        return list(self.iteritems())

    def __len__(self):
        return self.count

    def assoc(self, key, val):
        added_leaf = Box()
        start_root = self.root if self.root else BitmapIndexedNode.EMPTY
        new_root = start_root.assoc(0, key, val, added_leaf)

        if new_root is self.root:
            return self

        return PMap(self.count + 1 if added_leaf.val else self.count, new_root)

    def without(self, key):
        if self.root is None:
            return self

        new_root = self.root.without(0, key)

        if new_root is self.root:
            return self

        return PMap(self.count - 1, new_root)


_EMPTY_MAP = PMap(0, None)

# Idea, how about making a readonly class (by replacing __dict__) once the mapping
# and vector have been built up? In order to force the "purity" of immutability.
# Could also experiment with making the classes inner classes of the factory functions...

# Which name to choose... ?
def pmap(**kwargs):
    return pmapping(kwargs)


def pmapping(initial={}):
    map = _EMPTY_MAP
    for k, v in initial.iteritems():
        map = map.assoc(k, v)

    return map

# TODO: Rewrite the logic for hash collection detection to use two classes, one when there is a collision
# that contains a list of key value pairs and one when one single element exists that uses straight
# variables instead. Use __slots__ on these classes to minimize memory usage...
class PMap2(Mapping):
    def __init__(self, size, buckets):
        self.size = size
        self.buckets = buckets

    def _get_bucket(self, key):
        h = hash(key)
        index = h % len(self.buckets)
        bucket = self.buckets[index]
        return index, bucket

    def __getitem__(self, key):
        _, bucket = self._get_bucket(key)
        if bucket:
            for k, v in bucket:
                if k == key:
                    return  v

        raise KeyError

    def __iter__(self):
        return self.iterkeys()

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
        for bucket in self.buckets:
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
        return self.size

    def assoc(self, key, val):
        kv = (key, val)
        index, bucket = self._get_bucket(key)
        if bucket:
            # TODO: Break out handling of hash collisions to own classes
            for k, v in bucket:
                if k == key:
                    if v == val:
                        return self
                    else:
                        new_bucket = [(k2, v2) if k2 != k else (k2, val) for k2, v2 in bucket]
                        return PMap2(self.size, self.buckets.assoc(index, new_bucket))

            # TODO: Precalculate this value as an optimization?
            if len(self.buckets) < 0.67 * self.size:
                return PMap2(self.size, self._reallocate()).assoc(key, val)
            else:
                new_bucket = [kv]
                new_bucket.extend(bucket)
                new_buckets = self.buckets.assoc(index, new_bucket)

            return PMap2(self.size + 1, new_buckets)

        # Skip reallocation check if there was no conflict
        return PMap2(self.size + 1, self.buckets.assoc(index, [kv]))

    def without(self, key):
        # Should shrinking of the map ever be done if it becomes very small?
        index, bucket = self._get_bucket(key)

        if bucket:
            new_bucket = [(k, v) for (k, v) in bucket if k != key]
            if len(bucket) > len(new_bucket):
                return PMap2(self.size - 1, self.buckets.assoc(index, new_bucket if new_bucket else None))

        return self

    def _reallocate(self):
        new_list = 2 * len(self.buckets) * [None]
        new_len = len(new_list)
        for k, v in chain.from_iterable(x for x in self.buckets if x):
            index = hash(k) % new_len
            if new_list[index]:
                new_list[index].append((k, v))
            else:
                new_list[index] = [(k, v)]

        return pvector(new_list)

# Start of with eight elements
_EMPTY_MAP2 = PMap2(0, pvector(8*[None]))

def pmap2(**kwargs):
    return pmapping2(kwargs)


def pmapping2(initial={}):
    map = _EMPTY_MAP2
    for k, v in initial.iteritems():
        map = map.assoc(k, v)

    return map

##################### Pset ########################


class PSet(Set):
    def __init__(self, m):
        self.map = m

    def __contains__(self, element):
        return element in self.map

    def __iter__(self):
        return iter(self.map)

    def  __len__(self):
        return len(self.map)

    @classmethod
    def _from_iterable(cls, it):
        s = _EMPTY_SET
        for x in it:
            s = s.add(x)

        return s

    def toset(self):
        return set(self.map)

    def add(self, element):
        return PSet(self.map.assoc(element, True))

    def without(self, element):
        return PSet(self.map.without(element))

_EMPTY_SET = PSet(_EMPTY_MAP2)


def pset(elements=[]):
    return PSet._from_iterable(elements)