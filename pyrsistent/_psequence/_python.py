from enum import Enum
from functools import wraps
from itertools import groupby
from pyrsistent._transformations import transform
from pyrsistent._psequence._base import PSequenceBase, PSequenceEvolverBase

class PSequence(PSequenceBase):
    # no docstring - inherit docstring from PSequenceBase

    # Support structure for PSequence.

    # Fingertrees, digits, and nodes are all represented using the
    # same class for easier implementation.

    # Empty fingertrees are PSequence(type=Tree, size=0, items=[])
    # Single fingertrees are PSequence(type=Tree, size=N, items=[node])
    # Deep fingertrees are PSequence(type=Tree, size=N, items=[left,middle,right])

    # Value-type nodes (node1) are PSequence(type=Node, size=1, items=[value])

    __slots__ = ('_type', '_size', '_items')

    class _Type(Enum):
        Node = 0
        Digit = 1
        Tree = 2

    def __new__(cls, _type, _size, _items):
        self = super(PSequence, cls).__new__(cls)
        self._type = _type
        self._size = _size
        self._items = _items
        return self

    @staticmethod
    def _node1(value):
        return PSequence(PSequence._Type.Node, 1, (value,))
    @staticmethod
    def _node(size, *items):
        return PSequence(PSequence._Type.Node, size, items)
    @staticmethod
    def _nodeS(*items):
        size = sum(i._size for i in items)
        return PSequence(PSequence._Type.Node, size, items)

    @staticmethod
    def _digit(size, *items):
        return PSequence(PSequence._Type.Digit, size, items)
    @staticmethod
    def _digitS(*items):
        size = sum(i._size for i in items)
        return PSequence(PSequence._Type.Digit, size, items)

    @staticmethod
    def _single(item):
        return PSequence(PSequence._Type.Tree, item._size, (item,))
    @staticmethod
    def _deep(size, left, middle, right):
        return PSequence(PSequence._Type.Tree, size, (left, middle, right))
    @staticmethod
    def _deepS(left, middle, right):
        size = left._size + middle._size + right._size
        return PSequence(PSequence._Type.Tree, size, (left, middle, right))

    def _isnode1(self):
        return self._size == 1 and self._type == PSequence._Type.Node

    def _appendright(self, item):
        if self._size == 0:
            return PSequence._single(item)
        if len(self._items) == 1:
            return PSequence._deep(self._size + item._size,
                PSequence._digit(self._size, self._items[0]),
                _EMPTY_SEQUENCE,
                PSequence._digit(item._size, item))
        left, middle, right = self._items
        if len(right._items) < 4:
            return PSequence._deep(self._size + item._size,
                left, middle,
                PSequence._digit(right._size + item._size, *right._items, item))
        return PSequence._deep(self._size + item._size,
            left,
            middle._appendright(PSequence._nodeS(*right._items[:3])),
            PSequence._digitS(right._items[3], item))

    def appendright(self, value):
        return self._appendright(PSequence._node1(value))

    append = appendright

    def _appendleft(self, item):
        if self._size == 0:
            return PSequence._single(item)
        if len(self._items) == 1:
            return PSequence._deep(self._size + item._size,
                PSequence._digit(item._size, item),
                _EMPTY_SEQUENCE,
                PSequence._digit(self._size, self._items[0]))
        left, middle, right = self._items
        if len(left._items) < 4:
            return PSequence._deep(self._size + item._size,
                PSequence._digit(left._size + item._size, item, *left._items),
                middle, right)
        return PSequence._deep(self._size + item._size,
            PSequence._digitS(item, left._items[0]),
            middle._appendleft(PSequence._nodeS(*left._items[1:])),
            right)

    def appendleft(self, value):
        return self._appendleft(PSequence._node1(value))

    @property
    def right(self):
        if self._size == 0:
            raise IndexError('peek from empty sequence')
        if len(self._items) == 1:
            return self._items[0]._items[0]
        return self._items[2]._items[-1]._items[0]

    @property
    def left(self):
        if self._size == 0:
            raise IndexError('peek from empty sequence')
        if len(self._items) == 1:
            return self._items[0]._items[0]
        return self._items[0]._items[0]._items[0]

    def _pullright(self, left):
        if self._size == 0:
            return PSequence._fromnodes(left._size, left._items)
        init, last = self._viewright()
        return PSequence._deep(self._size + left._size,
            left, init, PSequence._digit(last._size, *last._items))

    def _viewright(self):
        if len(self._items) == 1:
            return _EMPTY_SEQUENCE, self._items[0]
        left, middle, right = self._items
        *init, last = right._items
        if not init: return middle._pullright(left), last
        init = PSequence._deep(self._size - last._size, left, middle,
            PSequence._digit(right._size - last._size, *init))
        return init, last

    def viewright(self):
        if self._size == 0:
            raise IndexError('peek from empty sequence')
        init, last =  self._viewright()
        return init, last._items[0]

    def _pullleft(self, right):
        if self._size == 0:
            return PSequence._fromnodes(right._size, right._items)
        head, tail = self._viewleft()
        return PSequence._deep(self._size + right._size,
            PSequence._digit(head._size, *head._items), tail, right)

    def _viewleft(self):
        if len(self._items) == 1:
            return self._items[0], _EMPTY_SEQUENCE
        left, middle, right = self._items
        head, *tail = left._items
        if not tail: return head, middle._pullleft(right)
        return head, PSequence._deep(self._size - head._size,
            PSequence._digit(left._size - head._size, *tail),
            middle, right)

    def viewleft(self):
        if self._size == 0:
            raise IndexError('peek from empty sequence')
        head, tail =  self._viewleft()
        return head._items[0], tail

    def view(self, *index):
        items, last, rest = [], 0, self
        for idx in index:
            idx = self._checkindex(idx)
            if idx < last: raise IndexError('indices must be in sorted order')
            left, item, rest = rest._splitview(idx - last)
            items.append(left)
            items.append(item._items[0])
            last = idx + 1
        items.append(rest)
        return tuple(items)

    def _checkindex(self, index):
        idx = index
        if index < 0: idx += self._size
        if not (0 <= idx < self._size):
            raise IndexError('index out of range: {}'.format(index))
        return idx

    def _splitindex(self, index):
        size = 0
        for mid, item in enumerate(self._items):
            size += item._size
            if size > index: break
        return (mid, item, size - item._size, self._items[:mid],
            self._size - size, self._items[mid+1:])

    def _splitview(self, index):
        if len(self._items) == 1:
            return _EMPTY_SEQUENCE, \
                self._items[0], \
                _EMPTY_SEQUENCE
        left, middle, right = self._items
        if index < left._size:
            mid, item, sizeL, itemsL, sizeR, itemsR = left._splitindex(index)
            left1 = PSequence._fromnodes(sizeL, itemsL)
            right1 = middle._pullleft(right) if not itemsR else \
                PSequence._deepS(PSequence._digitS(*itemsR), middle, right)
            return left1, item, right1
        index -= left._size
        if index < middle._size:
            left1, midT, right1 = middle._splitview(index)
            index -= left1._size
            mid, item, sizeL, itemsL, sizeR, itemsR = midT._splitindex(index)
            left2 = left1._pullright(left) if not itemsL else \
                PSequence._deepS(left, left1, PSequence._digit(sizeL, *itemsL))
            right2 = right1._pullleft(right) if not itemsR else \
                PSequence._deepS(PSequence._digit(sizeR, *itemsR), right1, right)
            return left2, item, right2
        index -=  middle._size
        mid, item, sizeL, itemsL, sizeR, itemsR = right._splitindex(index)
        left1 = middle._pullright(left) if not itemsL else \
            PSequence._deepS(left, middle, PSequence._digitS(*itemsL))
        right1 = PSequence._fromnodes(sizeR, itemsR)
        return left1, item, right1

    def splitat(self, index):
        try: index = self._checkindex(index)
        except IndexError:
            if index < 0: return _EMPTY_SEQUENCE, self
            return self, _EMPTY_SEQUENCE
        left, mid, right = self._splitview(index)
        return left, right._appendleft(mid)

    @staticmethod
    def _fromnodes(size, nodes):
        if len(nodes) == 0: return _EMPTY_SEQUENCE
        if len(nodes) == 1: return PSequence._single(nodes[0])
        if len(nodes) <= 8:
            mid = len(nodes) // 2
            return PSequence._deep(size,
                PSequence._digitS(*nodes[:mid]),
                _EMPTY_SEQUENCE,
                PSequence._digitS(*nodes[mid:]))
        left = PSequence._digitS(*nodes[:3])
        right = PSequence._digitS(*nodes[-3:])
        if len(nodes) % 3 == 0:
            most, rest = nodes[3:-3], []
        elif len(nodes) % 3 == 1:
            most, rest = nodes[3:-7], [nodes[-7:-5], nodes[-5:-3]]
        else:
            most, rest = nodes[3:-5], [nodes[-5:-3]]
        most = list(zip(*([iter(most)]*3)))
        merged = [PSequence._nodeS(*ns) for ns in most + rest]
        middle = PSequence._fromnodes(size - left._size - right._size, merged)
        return PSequence._deep(size, left, middle, right)

    def _takeleft(self, index):
        if len(self._items) == 1:
            return self._items[0], _EMPTY_SEQUENCE
        left, middle, right = self._items
        if index < left._size:
            mid, item, sizeL, itemsL, sizeR, itemsR = left._splitindex(index)
            return item, PSequence._fromnodes(sizeL, itemsL)
        index -= left._size
        if index < middle._size:
            node, left1 = middle._takeleft(index)
            mid, item, sizeL, itemsL, sizeR, itemsR = node._splitindex(index - left1._size)
            if not itemsL: return item, left1._pullright(left)
            return item, PSequence._deepS(left, left1,
                PSequence._digit(sizeL, *itemsL))
        index -= middle._size
        mid, item, sizeL, itemsL, sizeR, itemsR = right._splitindex(index)
        if not itemsL: return item, middle._pullright(left)
        return item, PSequence._deepS(left, middle,
            PSequence._digit(sizeL, *itemsL))

    def _takeL(self, count):
        if count <= 0: return _EMPTY_SEQUENCE
        if count >= self._size: return self
        return self._takeleft(count)[1]

    def _takeright(self, index):
        if len(self._items) == 1:
            return self._items[0], _EMPTY_SEQUENCE
        left, middle, right = self._items
        if index < right._size:
            mid, item, sizeL, itemsL, sizeR, itemsR = \
                right._splitindex(right._size - index - 1)
            return item, PSequence._fromnodes(sizeR, itemsR)
        index -= right._size
        if index < middle._size:
            node, right1 = middle._takeright(index)
            mid, item, sizeL, itemsL, sizeR, itemsR = \
                node._splitindex(node._size - index + right1._size - 1)
            if not itemsR: return item, right1._pullleft(right)
            return item, PSequence._deepS(
                PSequence._digit(sizeR, *itemsR),
                right1, right)
        index -= middle._size
        mid, item, sizeL, itemsL, sizeR, itemsR = \
            left._splitindex(left._size - index - 1)
        if not itemsR: return item, middle._pullleft(right)
        return item, PSequence._deepS(
            PSequence._digit(sizeR, *itemsR), middle, right)

    def _takeR(self, count):
        if count <= 0: return _EMPTY_SEQUENCE
        if count >= self._size: return self
        return self._takeright(count)[1]

    def _extend(self, other):
        if self._size == 0: return other
        if other._size == 0: return self
        if len(self._items) == 1: return other._appendleft(self._items[0])
        if len(other._items) == 1: return self._appendright(other._items[0])
        left1, middle1, right1 = self._items
        left2, middle2, right2 = other._items
        nodes = right1._items + left2._items
        if len(nodes) % 3 == 0:
            most, rest = nodes, []
        elif len(nodes) % 3 == 1:
            most, rest = nodes[:-4], [nodes[-4:-2], nodes[-2:]]
        else:
            most, rest = nodes[:-2], [nodes[-2:]]
        most = list(zip(*([iter(most)]*3)))
        for ns in most + rest:
            middle1 = middle1._appendright(PSequence._nodeS(*ns))
        return PSequence._deep(self._size + other._size,
            left1, middle1._extend(middle2), right2)

    def extendright(self, other):
        return self._extend(psequence(other))

    extend = extendright
    __add__ = extendright

    def extendleft(self, other):
        return psequence(other)._extend(self)

    __radd__ = extendleft

    def reverse(self):
        if self._isnode1(): return self
        return PSequence(self._type, self._size,
            tuple(i.reverse() for i in reversed(self._items)))

    @staticmethod
    def _sliceindices(slice, length):
        start, stop, step = slice.indices(length)
        if start < 0:
            start = -1 if step < 0 else 0
        elif start >= length:
            start = length - 1 if step < 0 else length
        if stop < 0:
            stop = -1 if step < 0 else 0
        elif stop >= length:
            stop = length - 1 if step < 0 else length
        count = 0
        if stop < start and step < 0:
            count = (start - stop - 1) // -step + 1
        elif start < stop and step > 0:
            count = (stop - start - 1) // step + 1
        return start, stop, step, count

    def _getitem(self, index):
        if len(self._items) == 1 and self._type == PSequence._Type.Node:
            return self._items[0]
        mid, item, sizeL, itemsL, sizeR, itemsR = self._splitindex(index)
        return item._getitem(index - sizeL)

    def _getslice(self, modulo, count, step, output):
        if count == 0: return modulo, count
        if self._size <= modulo: return modulo - self._size, count
        if len(self._items) == 1 and self._type == PSequence._Type.Node:
            output.append(self._items[0])
            return step, count - 1
        for item in self._items:
            modulo, count = item._getslice(modulo, count, step, output)
        return modulo, count

    def __getitem__(self, index):
        if isinstance(index, slice):
            start, stop, step, count = PSequence._sliceindices(index, self._size)
            if count <= 0: return _EMPTY_SEQUENCE
            if step < 0: start, stop = start + (count - 1) * step, start + 1
            if abs(step) == 1:
                tree = self
                if stop < self._size: tree = tree._takeL(stop)
                if start > 0: tree = tree._takeR(stop - start)
            else:
                output = []
                modulo, count = self._getslice(start, count, abs(step) - 1, output)
                tree = psequence(output)
            return tree if step > 0 else tree.reverse()
        index = self._checkindex(index)
        return self._getitem(index)

    def _setitem(self, index, value):
        if self._isnode1(): return PSequence._node1(value)
        items = list(self._items)
        for n, item in enumerate(items):
            if index < item._size: break
            index -= item._size
        items[n] = item._setitem(index, value)
        return PSequence(self._type, self._size, tuple(items))

    def _setslice(self, modulo, count, step, values):
        if count == 0: return self, modulo, count
        if self._size <= modulo: return self, modulo - self._size, count
        if len(self._items) == 1 and self._type == PSequence._Type.Node:
            return PSequence._node1(next(values)), step, count - 1
        items = []
        for item in self._items:
            item, modulo, count = item._setslice(modulo, count, step, values)
            items.append(item)
        return PSequence(self._type, self._size, tuple(items)), modulo, count

    def set(self, index, value):
        if isinstance(index, slice):
            start, stop, step, count = self._sliceindices(index, self._size)
            if step == 1:
                mid = psequence(value)
                return self._takeL(start) + mid + \
                    self._takeR(self._size - max(start, stop))
            if count == 0: return self
            if step < 0: start, stop = start + (count - 1) * step, start + 1
            try:
                len(value)
            except TypeError:
                value = list(value)
            if len(value) != count:
                raise ValueError('attempt to assign sequence of size '
                 + '{} to extended slice of size {}'.format(self._size, count))
            return self._setslice(start, count, abs(step) - 1,
                iter(value) if step > 0 else reversed(value))[0]
        index = self._checkindex(index)
        return self._setitem(index, value)

    def _mset(self, index, pairs):
        if not pairs: return index + self._size, self
        target = pairs[-1][0]
        if index + self._size <= target:
            return index + self._size, self
        if self._isnode1(): return index + 1, PSequence._node1(pairs.pop()[1])
        items = []
        for item in self._items:
            index, item = item._mset(index, pairs)
            items.append(item)
        return index, PSequence(self._type, self._size, tuple(items))

    def mset(self, *args):
        pairs, args = [], iter(args)
        for arg in args:
            if isinstance(arg, tuple):
                index, value = arg
            elif isinstance(arg, int):
                index, value = arg, next(args)
            else:
                raise TypeError('expected int or tuple but got {}'.format(type(arg)))
            pairs.append((self._checkindex(index), value))
        key = lambda x: x[0]
        pairs = [(index, list(group)[-1][1]) for index, group in
            groupby(sorted(pairs, key=key, reverse=True), key=key)]
        return self._mset(0, pairs)[1]

    def _mergeleftnode(self, item):
        if item is None: return (self,)
        if len(self._items) == 2:
            return (PSequence._node(self._size + item._size, item, *self._items),)
        return (PSequence._nodeS(item, self._items[0]),
            PSequence._nodeS(self._items[1], self._items[2]))

    def _mergerightnode(self, item):
        if item is None: return (self,)
        if len(self._items) == 2:
            return (PSequence._node(self._size + item._size, *self._items, item),)
        return (PSequence._nodeS(self._items[0], self._items[1]),
            PSequence._nodeS(self._items[2], item))

    def _deleteitem(self, index):
        if self._isnode1(): return False, None
        mid, item, sizeL, itemsL, sizeR, itemsR = self._splitindex(index)
        full, meld = item._deleteitem(index - sizeL)
        msize = 0 if meld is None else meld._size
        size = self._size - item._size + msize
        if full: return True, PSequence(self._type, size, itemsL + (meld,) + itemsR)
        if len(self._items) == 1: return False, meld
        if self._type != PSequence._Type.Tree:
            if meld is None:
                if self._type == PSequence._Type.Node and len(self._items) == 2:
                    return (False,) + itemsL + itemsR
                if self._type == PSequence._Type.Digit and len(self._items) == 1:
                    return False, None
            if itemsR: itemsR = itemsR[0]._mergeleftnode(meld) + itemsR[1:]
            else: itemsL = itemsL[:-1] + itemsL[-1]._mergerightnode(meld)
            items = itemsL + itemsR
            if self._type == PSequence._Type.Node and len(items) == 1:
                return (False,) + items
            return True, PSequence(self._type, size, itemsL + itemsR)
        left, middle, right = self._items
        if mid == 0:
            if middle._size == 0:
                return True, PSequence._fromnodes(size,
                    right._items[0]._mergeleftnode(meld) + right._items[1:])
            head, tail = middle._viewleft()
            leftT = PSequence._digit(head._size + msize,
                *head._items[0]._mergeleftnode(meld), *head._items[1:])
            return True, PSequence._deep(size, leftT, tail, right)
        if mid == 2:
            if middle._size == 0:
                return True, PSequence._fromnodes(size,
                    left._items[:-1] + left._items[-1]._mergerightnode(meld))
            init, last = middle._viewright()
            rightT = PSequence._digit(last._size + msize,
                *last._items[:-1], *last._items[-1]._mergerightnode(meld))
            return True, PSequence._deep(size, left, init, rightT)
        meld = tuple() if meld is None else (meld,)
        if len(right._items) < 4:
            return True, PSequence._deep(size, left,
                _EMPTY_SEQUENCE,
                PSequence._digitS(*meld, *right._items))
        return True, PSequence._deep(size, left,
            PSequence._single(PSequence._nodeS(*meld, *right._items[:2])),
            PSequence._digitS(*right._items[2:]))

    def _deleteslice(self, start, stop, step, count):
        acc, _, rest = self._splitview(start)
        step = abs(step) - 1
        for _ in range(count - 1):
            chunk, _, rest = rest._splitview(step)
            acc += chunk
        return acc + rest

    def delete(self, index):
        if isinstance(index, slice):
            start, stop, step, count = self._sliceindices(index, self._size)
            if count == 0: return self
            if step < 0: start, stop = start + (count - 1) * step, start + 1
            if abs(step) == 1: return self._takeL(start) + \
                self._takeR(self._size - max(start, stop))
            return self._deleteslice(start, stop, step, count)
        index = self._checkindex(index)
        full, meld = self._deleteitem(index)
        if not full: return _EMPTY_SEQUENCE
        return meld

    def _insert(self, index, value):
        if self._isnode1(): return value, self
        mid, item, sizeL, itemsL, sizeR, itemsR = self._splitindex(index)
        meld, extra = item._insert(index - sizeL, value)
        size = self._size + value._size
        if extra is None: return PSequence(self._type,
            size, itemsL + (meld,) + itemsR), None
        if self._type != PSequence._Type.Tree:
            items = itemsL + (meld, extra) + itemsR
            if self._type == PSequence._Type.Node and len(self._items) == 3:
                return PSequence._nodeS(*items[:2]), PSequence._nodeS(*items[2:])
            if self._type == PSequence._Type.Digit and len(self._items) == 4:
                return items, items[-1]
            return PSequence(self._type, size, items), None
        if len(self._items) == 1:
            return PSequence._deep(size,
                PSequence._digitS(meld),
                _EMPTY_SEQUENCE,
                PSequence._digitS(extra)), None
        left, middle, right = self._items
        if mid == 0: return PSequence._deep(size,
            PSequence._digitS(*meld[:2]),
            middle._appendleft(PSequence._nodeS(*meld[2:])),
            right), None
        return PSequence._deep(size, left,
            middle._appendright(PSequence._nodeS(*meld[:3])),
            PSequence._digitS(*meld[3:])), None

    def insert(self, index, value):
        try: index = self._checkindex(index)
        except IndexError:
            if index < 0: return self.appendleft(value)
            return self.appendright(value)
        return self._insert(index, PSequence._node1(value))[0]

    def remove(self, value):
        return self.delete(self.index(value))

    def transform(self, *transformations):
        return transform(self, transformations)

    def index(self, value):
        for n, x in enumerate(self):
            if value == x: return n
        raise ValueError('value not in sequence');

    def count(self, value):
        count = 0
        for x in self:
            if value == x:
                count += 1
        return count

    def chunksof(self, size):
        acc = []
        while self._size != 0:
            chunk, self = self.splitat(size)
            acc.append(chunk)
        return psequence(acc)

    def __reduce__(self):
        return psequence, (self.tolist(),)

    def __hash__(self):
        return hash(self.totuple())

    def _tolist(self, acc):
        if self._isnode1():
            acc.append(self._items[0])
        else:
            for item in self._items:
                item._tolist(acc)
        return acc

    def tolist(self):
        return self._tolist([])

    def totuple(self):
        return tuple(self.tolist())

    def __mul__(self, times):
        if times <= 0: return _EMPTY_SEQUENCE
        acc, exp = _EMPTY_SEQUENCE, self
        while times != 0:
            if times % 2 == 1:
                acc += exp
            exp = exp + exp
            times //= 2
        return acc

    __rmul__ = __mul__

    def __len__(self):
        return self._size

    @staticmethod
    def _compare1(xs, ys, equality):
        try: x = next(xs)
        except StopIteration:
            try: y = next(ys)
            except StopIteration: return 0
            return -1
        try: y = next(ys)
        except StopIteration: return 1
        if x == y: return None
        if equality or x > y: return 1
        return -1

    @staticmethod
    def _compare(xs, ys, equality):
        if equality:
            if xs is ys: return 0
            try:
                xlen, ylen = len(xs), len(ys)
            except TypeError:
                pass
            else:
                if xlen != ylen: return 1
        # compare by iteration
        xs, ys = iter(xs), iter(ys)
        cmp = PSequence._compare1(xs, ys, equality)
        while cmp is None:
            cmp = PSequence._compare1(xs, ys, equality)
        return cmp

    def __eq__(self, other):
        return PSequence._compare(self, other, True) == 0
    def __ne__(self, other):
        return PSequence._compare(self, other, True) != 0
    def __gt__(self, other):
        return PSequence._compare(self, other, False) > 0
    def __ge__(self, other):
        return PSequence._compare(self, other, False) >= 0
    def __lt__(self, other):
        return PSequence._compare(self, other, False) < 0
    def __le__(self, other):
        return PSequence._compare(self, other, False) <= 0

    def __repr__(self):
        return 'psequence({})'.format(list(self))

    __str__ = __repr__

    def sort(self, *args, **kwargs):
        xs = self.tolist()
        xs.sort(*args, **kwargs)
        return psequence(xs)

    def _totree(self):
        if self._isnode1(): return 'Node', 1, self._items[0]
        return (self._type.name, self._size,
            *(i._totree() for i in self._items))

    @staticmethod
    def _fromtree(tuples):
        ptype, size, *items = tuples
        ptype = PSequence._Type[ptype]
        if ptype == PSequence._Type.Node and size == 1:
            return PSequence._node1(items[0])
        return PSequence(ptype, size,
            tuple(PSequence._fromtree(i) for i in items))

    @staticmethod
    def _refcount():
        return 0, 0, 0

    def evolver(self):
        return Evolver(self)

    def __iter__(self):
        if self._isnode1():
            yield self._items[0]
            return
        for item in self._items:
            yield from item

    def __reversed__(self):
        if self._isnode1():
            yield self._items[0]
            return
        for item in reversed(self._items):
            yield from reversed(item)

class Evolver(PSequenceEvolverBase):
    __slots__ = ('_seq',)

    def __init__(self, _seq):
        self._seq = _seq

    def persistent(self):
        return self._seq

    def __repr__(self):
        return repr(self._seq) + '.evolver()'

    __str__ = __repr__

    @property
    def left(self):
        return self._seq.left

    @property
    def right(self):
        return self._seq.right

    def popleft(self):
        value, self._seq = self._seq.viewleft()
        return value

    def popright(self):
        self._seq, value = self._seq.viewright()
        return value

    def pop(self, index=None):
        if index is None: return self.popright()
        value = self[index]
        self.delete(index)
        return value

    def copy(self):
        return self._seq.evolver()

    evolver = copy

    def clear(self):
        self._seq = _EMPTY_SEQUENCE

    def __iadd__(self, other):
        self._seq = self._seq + other
        return self

    def __imul__(self, other):
        self._seq = self._seq * other
        return self

    # methods that query the sequence
    for _name in ['tolist', 'totuple', 'chunksof', 'count', 'index',
            'splitat', 'view', 'viewleft', 'viewright',
            '__eq__', '__ne__', '__ge__', '__gt__', '__le__', '__lt__',
            '__reduce__', '__getitem__', '__len__',
            '__iter__', '__reversed__', '_totree']:
        def _wrap(_name):
            func = getattr(PSequence, _name)
            @wraps(func)
            def _wrapper(self, *args, **kwargs):
                return func(self._seq, *args, **kwargs)
            return _wrapper
        locals()[_name] = _wrap(_name)

    # methods that create a new evolver
    for _name in ['__mul__', '__rmul__', '__add__', '__radd__']:
        def _wrap(_name):
            func = getattr(PSequence, _name)
            @wraps(func)
            def _wrapper(self, *args, **kwargs):
                return Evolver(func(self._seq, *args, **kwargs))
            return _wrapper
        locals()[_name] = _wrap(_name)

    # methods that modify the evolver
    for _name in ['reverse', 'transform',
            'append', 'appendright', 'appendleft',
            'extend', 'extendleft', 'extendright',
            'set', 'mset', 'insert', 'delete', 'remove', 'sort']:
        def _wrap(_name):
            func = getattr(PSequence, _name)
            @wraps(func)
            def _wrapper(self, *args, **kwargs):
                self._seq = func(self._seq, *args, **kwargs)
                return self
            return _wrapper
        locals()[_name] = _wrap(_name)

    __setitem__ = set
    __delitem__ = delete

_EMPTY_SEQUENCE = PSequence(PSequence._Type.Tree, 0, tuple())

def psequence(iterable=_EMPTY_SEQUENCE):
    if isinstance(iterable, Evolver): return iterable._seq
    if isinstance(iterable, PSequence): return iterable
    nodes = [PSequence._node1(i) for i in iterable]
    return PSequence._fromnodes(len(nodes), nodes)

__all__ = ('psequence', 'PSequence')
