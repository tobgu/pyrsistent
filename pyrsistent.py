from collections import Sequence, Mapping
import collections


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
        Should never be created directly, use the pvector() factory function instead.
        """
        self._count = c
        self._shift = s
        self._root = r
        self._tail = t
        self._set_focus(t, self._count)

    def _set_focus(self, node, index):
        # The focus is a kind of cache for the last node that was accessed for reading
        # it is used to speed up reading of nearby values.
        # It does make the vector mutable internally but it is never exposed to the outside,
        # I couldn't come up with any negative aspects of it (except for ugliness perhaps)
        # but that doesn't mean there aren't any... This is kind of cheating on the immutability
        # though, not sure if it should be kept. If it is to be kept then it could probably be
        # explored further so that the focus is brought along to any new vectors created
        # by "modifying" this one. As it is right now the focus is always set to the tail
        # initially.

        # Need to set the focus atomically (as one reference) to be thread safe
        self._focus = {'node': node, 'index': (index >> SHIFT) << SHIFT}

    def __len__(self):
        return self._count
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            indices = index.indices(len(self))
            return pvector([self._list_for(i)[i & BIT_MASK] for i in range(*indices)])

        return self._list_for(index)[index & BIT_MASK]

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
            subidx = (i >> level) & BIT_MASK  # >>>
            ret[subidx] = self._do_assoc(level - SHIFT, node[subidx], i, val)
            
        return ret

    def _tail_offset(self):
        return self._count - len(self._tail)

    def _list_for(self, i):
        if 0 <= i < self._count:
            # Need to keep the reference to the focus locally to make sure that it
            # isn't tampered with while we are using it.
            focus = self._focus
            if (i >> SHIFT) << SHIFT == focus['index']:
                return focus['node']

            if i >= self._tail_offset():
                self._set_focus(self._tail, i)
                return self._tail

            node = self._root
            for level in range(self._shift, 0, -SHIFT):
                node = node[(i >> level) & BIT_MASK]  # >>>

            self._set_focus(node, i)
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

    def _transient_insert_tail(self):
        self._root, self._shift = self._create_new_root()
        self._tail = []

    def _transient_extend_iterator(self, iterator):
        try:
            while 1:
                while len(self._tail) < BRANCH_FACTOR:
                    self._tail.append(iterator.next())
                    self._count += 1

                self._transient_insert_tail()

        except StopIteration:
            # We're done
            pass

    def extend(self, obj):
        # Uses methods that mutates the object directly to speed
        # up construction of large vectors from lists
        if isinstance(obj, collections.Sequence):
            return self._extend_sequence(obj)

        return self._extend_iterator(obj)

    def _extend_iterator(self, iterator):
        try:
            new_vector = self.append(next(iterator))
            new_vector._transient_extend_iterator(iterator)
            return new_vector
        except StopIteration:
            # Empty container, nothing to extend with
            return self

    def _transient_extend_sequence(self, sequence):
        offset = 0
        sequence_len = len(sequence)
        while offset < sequence_len:
            max_delta_len = BRANCH_FACTOR - len(self._tail)
            delta = sequence[offset:offset + max_delta_len]
            self._tail.extend(delta)
            delta_len = len(delta)
            self._count += delta_len
            offset += delta_len

            if len(self._tail) == BRANCH_FACTOR:
                self._transient_insert_tail()

    def _extend_sequence(self, c):
        if c:
            new_vector = self.append(c[0])
            new_vector._transient_extend_sequence(c[1:])
            return new_vector
        else:
            # Empty container, nothing to extend with
            return self


    def _push_tail(self, level, parent, tail_node):
        """
        if parent is leaf, insert node,
        else does it map to an existing child? ->
             node_to_insert = push node one more level
        else alloc new path

        return  node_to_insert placed in copy of parent
        """
        subidx = ((self._count - 1) >> level) & BIT_MASK # >>>
        ret = list(parent)

        if level == SHIFT:
            ret.append(tail_node)
        else:
            if len(parent) > subidx:
                ret[subidx] = self._push_tail(level - SHIFT, parent[subidx], tail_node)
            else:
                ret.append(self._new_path(level - SHIFT, tail_node))

        return ret



_EMPTY_VECTOR = PVector(0, SHIFT, [], [])

def empty_list(length):
    return [None for x in range(length)]

def pvector(elements=[]):
    vec = _EMPTY_VECTOR
    return vec.extend(elements)

class Box(object):
    def __init__(self, val = None):
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
            
            # Create a copy of with size + 2 to hold the new element 
            new_array = list(self.array)
            new_array.append(key)
            new_array.append(val)
            added_leaf.val = added_leaf
            return HashCollisionNode(the_hash, new_array)
         
        # Another hash, nest ourselves in a bitmap indexed node
        return BitmapIndexedNode(bitpos(self.hash, shift), [None, self]).assoc(shift, key, val, added_leaf)

    def find(self, shift, key, not_found):
        idx = self.find_index(key)
        if idx < 0:
            return not_found
        
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
                             clone_and_set(self.array, idx, BitmapIndexedNode.EMPTY.assoc(shift + SHIFT, key, val, added_leaf)))
        
        n = node.assoc(shift + SHIFT, key, val, added_leaf)
        if n is node:
            return self
        
        return ArrayNode(self.count, clone_and_set(self.array, idx, n))
    
    def find(self, shift, key, not_found):
        hash_value = hash(key)
        idx = mask(hash_value, shift)
        node = self.array[idx]
        if node is None:
            return not_found
        
        return node.find(shift + SHIFT, key, not_found)


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
            val_or_node = self.array[i+1]
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
            key_or_none = self.array[2*idx]
            val_or_node = self.array[2*idx+1]
            if key_or_none is None:
                # Node
                node = val_or_node.assoc(shift + SHIFT, key, val, added_leaf)
                if node is val_or_node:
                    return self
                return BitmapIndexedNode(self.bitmap, clone_and_set(self.array, 2*idx+1, node))

            if key == key_or_none:
                # BitmapIndexedNode, replace existing value
                if val is val_or_node:
                    return self
                return BitmapIndexedNode(self.bitmap, clone_and_set(self.array, 2*idx+1, val))

            # BitmapIndexedNode, add new value
            added_leaf.val = added_leaf
            return BitmapIndexedNode(self.bitmap, 
                  clone_and_set2(self.array,
                        2*idx, None, 
                        2*idx+1, create_node(shift + SHIFT, key_or_none, val_or_node, key, val)))
        else:
            # Unique hash_value value
            n = bitcount(self.bitmap)
            if n >= (BRANCH_FACTOR / 2):
                # This node is full. Need to convert this node to an ArrayNode.
                nodes = empty_list(BRANCH_FACTOR)
                jdx = mask(hash_value, shift)
                nodes[jdx] = BitmapIndexedNode.EMPTY.assoc(shift + SHIFT, key, val, added_leaf)
                # Copy all values
                j = 0
                for i in range(BRANCH_FACTOR):
                    if (self.bitmap >> i) & 1: # >>>
                        if self.array[j] is None:
                            # Sub node
                            nodes[i] = self.array[j+1]
                        else:
                            # key - value pair
                            nodes[i] = BitmapIndexedNode.EMPTY.assoc(shift + SHIFT, self.array[j], self.array[j+1], added_leaf)
                        j += 2
                return ArrayNode(n + 1, nodes)
            else:
               new_array = self.array[:2*idx]
               new_array.append(key)
               new_array.append(val)
               added_leaf.val = added_leaf
               new_array.extend(self.array[2*idx:])
               return BitmapIndexedNode(self.bitmap | bit, new_array)


    def find(self, shift, key, not_found):
         bit = bitpos(hash(key), shift)
         if (self.bitmap & bit) == 0:
            return not_found
         idx = self.index(bit)
         key_or_none = self.array[2*idx]
         val_or_node = self.array[2*idx+1]
         if key_or_none is None:
            return val_or_node.find(shift + SHIFT, key, not_found)
         
         if key == key_or_none:
            return val_or_node

         return not_found
        
    def  without(self, shift, key):
        the_hash = hash(key)
        bit = bitpos(the_hash, shift)
        
        if (self.bitmap & bit) == 0:
            return self
        
        idx = self.index(bit)
        key_or_none = self.array[2*idx]
        val_or_node = self.array[2*idx+1]
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
        return self.root.find(0, key, None) if self.root else None
    
    def __iter__(self):
        return iter(self.root if self.root else [])

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

def pmap(initial={}):
    map = _EMPTY_MAP
    for k, v in initial.iteritems():
        map = map.assoc(k, v)
    return map
    