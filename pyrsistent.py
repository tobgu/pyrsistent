from collections import Sequence, Mapping

def bitcount(val):
    return bin(val).count("1")

BRANCH_FACTOR = 32
BIT_MASK = BRANCH_FACTOR - 1
SHIFT = bitcount(BIT_MASK)

class PVector(Sequence):
    
    def __init__(self, c, s, r, t):
        self.cnt = c
        self.shift = s
        self.root = r
        self.tail = t
        
    def __len__(self):
        return self.cnt
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            indices = index.indices(len(self))
            return pvector([self[i] for i in range(*indices)])

        node = self._array_for(index)
        return node[index & BIT_MASK]
    
    def assoc(self, i, val):
        if(i >= 0 and i < self.cnt):
            if(i >= self._tailoff()):
                new_tail = list(self.tail)
                new_tail[i & BIT_MASK] = val
                return PVector(self.cnt, self.shift, self.root, new_tail)

            return PVector(self.cnt, self.shift, self.do_assoc(self.shift, self.root, i, val), self.tail)
        
        if(i == self.cnt):
            return self.append(val)

        raise IndexError()

    def do_assoc(self, level, node, i, val):
        ret = list(node)
        if(level == 0):
            ret[i & BIT_MASK] = val
        else:
            subidx = (i >> level) & BIT_MASK  # >>>
            ret[subidx] = self.do_assoc(level - SHIFT, node[subidx], i, val)
            
        return ret;
        
    def _tailoff(self):
        if(self.cnt < BRANCH_FACTOR):
            return 0
        return ((self.cnt - 1) >> SHIFT) << SHIFT # >>>

    def _array_for(self, i):
        if(i >= 0 and i < self.cnt):
            if(i >= self._tailoff()):
                return self.tail
            node = self.root
            for level in range(self.shift, 0, -SHIFT):
                node = node[(i >> level) & BIT_MASK] # >>>
            return node
        
        raise IndexError();
    
    def append(self, val):
        #room in tail?
        if((self.cnt - self._tailoff()) < BRANCH_FACTOR):
            new_tail = list(self.tail)
            new_tail.append(val)
            return PVector(self.cnt + 1, self.shift, self.root, new_tail)
        
        # Full tail, push into tree
        new_shift = self.shift
        # Overflow root?
        if((self.cnt >> SHIFT) > (1 << self.shift)): # >>>
            new_root = [self.root, self.new_path(self.shift, self.tail)]
            new_shift += SHIFT
        else:
            new_root = self.push_tail(self.shift, self.root, self.tail)
    
        return PVector(self.cnt + 1, new_shift, new_root, [val])

    def new_path(self, level, node):
        if(level == 0):
            return node

        return [self.new_path(level - SHIFT, node)]

    def push_tail(self, level, parent, tail_node):
        """
        if parent is leaf, insert node,
        else does it map to an existing child? -> 
             node_to_insert = push node one more level
        else alloc new path
        
        return  node_to_insert placed in copy of parent
        """
        subidx = ((self.cnt - 1) >> level) & BIT_MASK # >>>
        node_to_insert = []
        ret = list(parent)

        if(level == SHIFT):
            ret.append(tail_node)
        else:
            if (len(parent) > subidx):
                ret[subidx] = self.push_tail(level - SHIFT, parent[subidx], tail_node) 
            else:
                ret.append(self.new_path(level - SHIFT, tail_node))

        return ret
    
_EMPTY_VECTOR = PVector(0, SHIFT, [], [])

def empty_list(length):
    return [None for x in range(length)]

def pvector(elements=[]):
    vec = _EMPTY_VECTOR
    for e in elements:
        vec = vec.append(e)
    return vec

class Box(object):
    def __init__(self, val = None):
        self.val = val

def mask(hash, shift):
    return (hash >> shift) & BIT_MASK # >>>
  
def bitpos(hash, shift):
    return 1 << mask(hash, shift)

def removePair(array, index):
    return array[:2 * index] + array[2 * (index + 1):]


class HashCollisionNode(object):
    def __init__(self, hash, array):
        self.hash = hash
        self.array = array

    def findIndex(self, key):
         for i in range(0, 2 * self.count(), 2):
            if key == self.array[i]:
               return i
         return -1
     
    def __iter__(self):
        for i in range(0, 2 * self.count(), 2):
            yield (self.array[i], self.array[i + 1])
            
    def assoc(self, shift, key, val, addedLeaf):
        the_hash = hash(key)
        if the_hash == self.hash:
            idx = self.findIndex(key)
            if idx != -1:
                if self.array[idx + 1] is val:
                    return self
                
                # Copy with new value
                return HashCollisionNode(self.hash, cloneAndSet(self.array, idx + 1, val))
            
            # Create a copy of with size + 2 to hold the new element 
            new_array = list(self.array)
            new_array.append(key)
            new_array.append(val)
            addedLeaf.val = addedLeaf;
            return HashCollisionNode(the_hash, new_array);
         
        # Another hash, nest ourself in a bitmap indexed node
        return BitmapIndexedNode(bitpos(self.hash, shift), [None, self]).assoc(shift, key, val, addedLeaf)

    def find(self, shift, key, notFound):
        idx = self.findIndex(key)
        if idx < 0:
            return notFound
        
        return self.array[idx + 1]

    def count(self):
        return len(self.array) / 2

    def without(self, shift, key):
        # Shift parameter not used here but must exist to adhere to Node protocol
        idx = self.findIndex(key)
        if idx == -1:
            return self
        
        if self.count() == 1:
            return None
        
        return HashCollisionNode(self.hash, removePair(self.array, idx / 2))

      
def createNode(shift, key1, val1, key2, val2):
      key1hash = hash(key1)
      key2hash = hash(key2)
      if(key1hash == key2hash):
         return HashCollisionNode(key1hash, [key1, val1, key2, val2])
     
      _ = Box()
      return BitmapIndexedNode.EMPTY \
            .assoc(shift, key1, val1, _) \
            .assoc(shift, key2, val2, _)

def cloneAndSet(original, index, value):
    clone = list(original)
    clone[index] = value
    return clone

def cloneAndSet2(original, index1, value1, index2, value2):
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

    def assoc(self, shift, key, val, addedLeaf):
        hash_value = hash(key)
        idx = mask(hash_value, shift)
        node = self.array[idx]
        
        if node == None:
            return ArrayNode(self.count + 1, 
                             cloneAndSet(self.array, idx, BitmapIndexedNode.EMPTY.assoc(shift + SHIFT, key, val, addedLeaf)))
        
        n = node.assoc(shift + SHIFT, key, val, addedLeaf)
        if(n is node):
            return self
        
        return ArrayNode(self.count, cloneAndSet(self.array, idx, n))
    
    def find(self, shift, key, notFound):
        hash_value = hash(key)
        idx = mask(hash_value, shift)
        node = self.array[idx]
        if node == None:
            return notFound
        
        return node.find(shift + SHIFT, key, notFound)


    def without(self, shift, key):
        key_hash = hash(key)
        idx = mask(key_hash, shift)
        node = self.array[idx]
        if node == None:
            return self
        
        n = node.without(shift + SHIFT, key)
        if n is node:
            return self
        elif n == None:
            # TODO: Removed packing optimization if size <= 8 here temporarily...
            return ArrayNode(self.count - 1, cloneAndSet(self.array, idx, n))
        else: 
            return ArrayNode(self.count, cloneAndSet(self.array, idx, n))

class BitmapIndexedNode(object):
    
    def __iter__(self):
        for i in xrange(0, len(self.array), 2):
            key_or_none = self.array[i]
            val_or_node = self.array[i+1]
            if key_or_none == None:
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
            keyOrNone = self.array[2*idx]
            valOrNode = self.array[2*idx+1]
            if keyOrNone == None:
                # Node
                node = valOrNode.assoc(shift + SHIFT, key, val, added_leaf)
                if node is valOrNode:
                    return self
                return BitmapIndexedNode(self.bitmap, cloneAndSet(self.array, 2*idx+1, node))

            if key == keyOrNone:
                # BitmapIndexedNode, replace existing value
                if val is valOrNode:
                    return self
                return BitmapIndexedNode(self.bitmap, cloneAndSet(self.array, 2*idx+1, val))

            # BitmapIndexedNode, add new value
            added_leaf.val = added_leaf;
            return BitmapIndexedNode(self.bitmap, 
                  cloneAndSet2(self.array, 
                        2*idx, None, 
                        2*idx+1, createNode(shift + SHIFT, keyOrNone, valOrNode, key, val)))
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
                        if self.array[j] == None:
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


    def find(self, shift, key, notFound):
         bit = bitpos(hash(key), shift)
         if (self.bitmap & bit) == 0:
            return notFound
         idx = self.index(bit)
         keyOrNull = self.array[2*idx]
         valOrNode = self.array[2*idx+1]
         if keyOrNull == None:
            return valOrNode.find(shift + SHIFT, key, notFound)
         
         if key == keyOrNull:
            return valOrNode

         return notFound
        
    def  without(self, shift, key):
        the_hash = hash(key)
        bit = bitpos(the_hash, shift)
        
        if (self.bitmap & bit) == 0:
            return self
        
        idx = self.index(bit)
        keyOrNull = self.array[2*idx]
        valOrNode = self.array[2*idx+1]
        if keyOrNull == None:
            n = valOrNode.without(shift + SHIFT, key)
            if n == valOrNode:
                return self
            if n != None:
                return BitmapIndexedNode(self.bitmap, cloneAndSet(self.array, 2 * idx + 1, n))
            if self.bitmap == bit:
                # Last value in this node
                return None
            return BitmapIndexedNode(self.bitmap ^ bit, removePair(self.array, idx))

        if key == keyOrNull:
            # TODO: collapse
            return BitmapIndexedNode(self.bitmap ^ bit, removePair(self.array, idx))
         
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
      
      if(new_root is self.root):
         return self
      
      return PMap(self.count + 1 if added_leaf.val else self.count, new_root)

    def without(self, key):
        if self.root == None:
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
    