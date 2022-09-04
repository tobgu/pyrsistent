from abc import ABCMeta, abstractmethod

class PSequenceBase(metaclass=ABCMeta):
    """
    Persistent sequence/list.
    Meant as a replacement for the cases where
    you would normally use a Python list or deque.

    Tries to follow the same naming conventions
    as the built in list/deque where feasible.

    Do not instantiate directly, instead use the factory
    functions `sq` or `psequence` to create an instance.

    The PSequence implements the Sequence protocol and is Hashable.

    Most operations are a constant factor (around 2x-3x) slower than the
    equivalent list operation. However, some are asymptotically faster:

        - inserting or deleting an item at either end is O(1)
        - inserting or deleting an item in the middle is O(log(n))
        - slicing a continguous chunk is O(log(n))
        - merging two sequences is O(log(n))
        - repeating a sequence k times is O(log(k)log(n))
          and takes O(log(k)log(n)) space

    The implementation uses 2-3 finger trees annotated with sizes
    based on Haskell's Data.Sequence from the package containers,
    which is described in

        - Ralf Hinze and Ross Paterson,
          "Finger trees: a simple general-purpose data structure",
          Journal of Functional Programming 16:2 (2006) pp 197-217.
          http://www.staff.city.ac.uk/~ross/papers/FingerTree.html

    Notable differences from the Haskell and
    Hinze/Patterson implementation include:

        - the Measure typeclass is stored as the field `size`
        - the Node and Element types are merged into a single type,
          with `size = 1` for Elements and `size > 1` for Nodes
        - the Digit and Node types are converted from sum types to
          a single product type, storing child Nodes in the field `items`
        - the Digit type stores its size
        - in the C implementation, the Deep constructor is converted into its
          own type to avoid packing FingerTree with three extra pointers
        - indexing by negative indices operates on items starting from the right

    The following are examples of some common operations on persistent sequences:

    >>> seq1 = psequence([1, 2, 3])
    >>> seq2 = seq1.append(4)
    >>> seq3 = seq1 + seq2
    >>> seq1
    psequence([1, 2, 3])
    >>> seq2
    psequence([1, 2, 3, 4])
    >>> seq3
    psequence([1, 2, 3, 1, 2, 3, 4])
    >>> seq3[3]
    1
    >>> seq3[2:5]
    psequence([3, 1, 2])
    >>> seq1.set(1, 99)
    psequence([1, 99, 3])
    """

    @abstractmethod
    def __eq__(self, other):
        """
        `O(n)`. Return self == other.

         >>> psequence([1,2,3]) == psequence([1,2,3])
         True
         >>> psequence([1,2,3]) == psequence([2,3,4])
         False
        """

    @abstractmethod
    def __ne__(self, other):
        """
        `O(n)`. Return self != other.

         >>> psequence([1,2,3]) != psequence([1,2,3])
         False
         >>> psequence([1,2,3]) != psequence([2,3,4])
         True
        """

    @abstractmethod
    def __le__(self, other):
        """
        `O(n)`. Return self <= other.

         >>> psequence([1,2,3]) <= psequence([1,2,3])
         True
         >>> psequence([1,2,3]) <= psequence([2,3,4])
         True
         >>> psequence([1,2,3]) <= psequence([0,1,2])
         False
        """

    @abstractmethod
    def __lt__(self, other):
        """
        `O(n)`. Return self < other.

         >>> psequence([1,2,3]) < psequence([1,2,3])
         False
         >>> psequence([1,2,3]) < psequence([2,3,4])
         True
         >>> psequence([1,2,3]) < psequence([0,1,2])
         False
        """

    @abstractmethod
    def __ge__(self, other):
        """
        `O(n)`. Return self >= other.

         >>> psequence([1,2,3]) >= psequence([1,2,3])
         True
         >>> psequence([1,2,3]) >= psequence([2,3,4])
         False
         >>> psequence([1,2,3]) >= psequence([0,1,2])
         True
        """

    @abstractmethod
    def __gt__(self, other):
        """
        `O(n)`. Return self > other.

         >>> psequence([1,2,3]) > psequence([1,2,3])
         False
         >>> psequence([1,2,3]) > psequence([2,3,4])
         False
         >>> psequence([1,2,3]) > psequence([0,1,2])
         True
        """

    @abstractmethod
    def extendleft(self, other):
        """
        Concatenate two sequences.

        `O(log(min(n,k)))` extend with PSequence
        `O(log(n)+k)` extend with iterable

        >>> psequence([1,2]).extendleft([3,4])
        psequence([3, 4, 1, 2])
        """

    @abstractmethod
    def extendright(self, other):
        """
        Concatenate two sequences.

        `O(log(min(n,k)))` extend with PSequence
        `O(log(n)+k)` extend with iterable

        >>> psequence([1,2]).extend([3,4])
        psequence([1, 2, 3, 4])
        >>> psequence([1,2]).extendright([3,4])
        psequence([1, 2, 3, 4])
        >>> psequence([1,2]) + [3,4]
        psequence([1, 2, 3, 4])
        """

    extend = extendright
    __add__ = extendright

    @abstractmethod
    def __getitem__(self, index):
        """
        Get the element(s) at the specified position(s).

        Time complexities for `n[i]`:
        `O(log(min(i,n−i)))` getting a single item.
        `O(log(max(i,m)))` getting a contiguous slice.
        `O(log(n)+m)` getting a non-contiguous slice.

        >>> psequence([1,2,3,4])[2]
        3
        >>> psequence([1,2,3,4,5])[1:4]
        psequence([2, 3, 4])
        >>> psequence([1,2,3,4])[5]
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def set(self, index, value):
        """
        Replace the element(s) at the specified position(s).

        Time complexities for `n.set(i,x)`:
        `O(log(min(i,n−i)))` replacing a single item.
        `O(log(max(n,m)))` replacing a contiguous slice.
        `O(max(log(n),m))` replacing a non-contiguous slice.

        >>> psequence([1,2,3,4]).set(2, 0)
        psequence([1, 2, 0, 4])
        >>> psequence([1,2,3,4,5]).set(slice(1,4), [-1,-2,-3])
        psequence([1, -1, -2, -3, 5])
        >>> psequence([1,2,3,4]).set(5, 0)
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def mset(self, *values):
        """
        `O(n+klogk)`. Replace multiple elements.

        >>> psequence([1,2,3,4]).mset(2, 0, 3, 5)
        psequence([1, 2, 0, 5])
        >>> psequence([1,2,3,4]).mset((2, 0), (3, 5))
        psequence([1, 2, 0, 5])
        >>> psequence([1,2,3,4]).mset(5, 0)
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def insert(self, index, value):
        """
        `O(log(min(i,n−i)))`. Insert an element at the specified position.

        >>> psequence([1,2,3,4]).insert(2, 0)
        psequence([1, 2, 0, 3, 4])
        >>> psequence([1,2,3,4]).insert(-10, 0)
        psequence([0, 1, 2, 3, 4])
        >>> psequence([1,2,3,4]).insert(10, 0)
        psequence([1, 2, 3, 4, 0])
        """


    @abstractmethod
    def delete(self, index):
        """
        Delete the element(s) at the specified position(s).

        Time complexities for `n.delete(i)`:
        `O(log(min(i,n−i)))` deleting a single item.
        `O(log(n))` deleting a contiguous slice.
        `O(n*log(k)/k)` deleting a non-contiguous slice.

        >>> psequence([1,2,3,4]).delete(2)
        psequence([1, 2, 4])
        >>> psequence([1,2,3,4,5]).delete(slice(1,4))
        psequence([1, 5])
        >>> psequence([1,2,3,4]).delete(5)
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def remove(self, value):
        """
        `O(log(min(i,n−i)))`. Remove an element by value.

        >>> psequence([1,2,3,4]).remove(2)
        psequence([1, 3, 4])
        >>> psequence([1,2,3,4]).remove(0)
        Traceback (most recent call last):
        ...
        ValueError: ...
        """

    @abstractmethod
    def __mul__(self, times):
        """
        `O(log(n)log(k))`. Repeat the sequence k times.

        >>> psequence([1,2,3]) * 3
        psequence([1, 2, 3, 1, 2, 3, 1, 2, 3])
        >>> 3 * psequence([1,2,3])
        psequence([1, 2, 3, 1, 2, 3, 1, 2, 3])
        """

    __rmul__ = __mul__

    @abstractmethod
    def __hash__(self):
        """
        ``O(n)`. Calculate the hash of the sequence.`

        >>> x1 = psequence([1,2,3,4])
        >>> x2 = psequence([1,2,3,4])
        >>> hash(x1) == hash(x2)
        True
        """

    @abstractmethod
    def __iter__(self):
        """
        `O(1)`. Create an iterator.

        Iterating the entire sequence is `O(n)`.

        >>> i = iter(psequence([1,2,3]))
        >>> next(i)
        1
        >>> next(i)
        2
        >>> next(i)
        3
        >>> next(i)
        Traceback (most recent call last):
        ...
        StopIteration
        """

    @abstractmethod
    def __reversed__(self):
        """
        `O(1)`. Create a reverse iterator.

        Iterating the entire sequence is `O(n)`.

        >>> i = reversed(psequence([1,2,3]))
        >>> next(i)
        3
        >>> next(i)
        2
        >>> next(i)
        1
        >>> next(i)
        Traceback (most recent call last):
        ...
        StopIteration
        """

    @abstractmethod
    def __len__(self):
        """
        `O(1)`. Get the length of the sequence.

        >>> len(psequence([1,2,3,4]))
        4
        """


    @abstractmethod
    def __reduce__(self):
        """
        `O(n)`. Support method for pickling.

        >>> func, args = psequence([1,2,3,4]).__reduce__()
        >>> func(*args)
        psequence([1, 2, 3, 4])
        """

    @abstractmethod
    def __repr__(self):
        """
        `O(n)`. Get a formatted string representation of the sequence.

        >>> repr(psequence([1,2,3]))
        'psequence([1, 2, 3])'
        """

    __str__ = __repr__

    @abstractmethod
    def appendleft(self, value):
        """
    	`O(1)`. Add an element to the left end of a sequence.

        >>> psequence([1,2,3]).appendleft(0)
        psequence([0, 1, 2, 3])
        """

    @abstractmethod
    def appendright(self, value):
        """
        `O(1)`. Add an element to the right end of a sequence.

        >>> psequence([1,2,3]).append(4)
        psequence([1, 2, 3, 4])
        >>> psequence([1,2,3]).appendright(4)
        psequence([1, 2, 3, 4])
        """

    append = appendright

    @abstractmethod
    def count(self, value):
        """
        `O(n)`. Count the number of times a value appears in the sequence.

        >>> psequence([1,2,3,3,4]).count(3)
        2
        """

    @abstractmethod
    def index(self, value):
        """
        `O(n)`. Find the first index of a value.

        >>> psequence([1,2,3,4]).index(3)
        2
        >>> psequence([]).index(3)
        Traceback (most recent call last):
        ...
        ValueError: ...
        """

    @abstractmethod
    def splitat(self, index):
        """
        `O(log(min(i,n−i)))`. Split a sequence at a given position.

        Equivalent to `(seq.take(i), seq.drop(i)).
        Does not raise IndexError, unlike `view`.

        >>> psequence([1,2,3,4]).splitat(2)
        (psequence([1, 2]), psequence([3, 4]))
        >>> psequence([1,2,3,4]).splitat(5)
        (psequence([1, 2, 3, 4]), psequence([]))
        >>> psequence([1,2,3,4]).splitat(-1)
        (psequence([1, 2, 3]), psequence([4]))
        >>> psequence([1,2,3,4]).splitat(-5)
        (psequence([]), psequence([1, 2, 3, 4]))
        """

    @abstractmethod
    def chunksof(self, size):
        """
        `O(nlog(n)/k)`. Split the sequence into chunks.

        >>> psequence([1,2,3,4,5,6,7,8]).chunksof(3)
        psequence([psequence([1, 2, 3]), psequence([4, 5, 6]), psequence([7, 8])])
        """

    @property
    @abstractmethod
    def left(self):
        """
        `O(1)`. Extract the first element.

        >>> psequence([1,2,3,4]).left
        1
        >>> psequence([]).left
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @property
    @abstractmethod
    def right(self):
        """
        `O(1)`. Extract the last element.

        >>> psequence([1,2,3,4]).right
        4
        >>> psequence([]).right
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def viewleft(self):
        """
        `O(1)`. Analyse the left end of a sequence.

        >>> psequence([1,2,3,4]).viewleft()
        (1, psequence([2, 3, 4]))
        >>> psequence([]).viewleft()
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def viewright(self):
        """
        `O(1)`. Analyse the right end of a sequence.

        >>> psequence([1,2,3,4]).viewright()
        (psequence([1, 2, 3]), 4)
        >>> psequence([]).viewright()
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def view(self, *index):
        """
        `O(klog(n))`. Split a sequence on the given position(s).

        Useful for pattern matching:

        >>> # doctest: +SKIP
        ... def match_on_view(seq):
        ...     match seq.view(0, 1, 4):
        ...         case (_, x0, _, x1, x_2_3, x4, _, rest):
        ...             pass

        Equivalent to `(seq[:i1], seq[i1], seq[i1+1:i2],
        seq[i2], seq[i2+1:i3], ..., seq[in+1:])`.

        >>> psequence([1,2,3,4]).view(0)
        (psequence([]), 1, psequence([2, 3, 4]))
        >>> psequence([1,2,3,4]).view(1)
        (psequence([1]), 2, psequence([3, 4]))
        >>> psequence([1,2,3,4]).view(1, 3)
        (psequence([1]), 2, psequence([3]), 4, psequence([]))
        >>> psequence([1,2,3,4]).view(5)
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def reverse(self):
        """
        `O(n)`. Reverse the sequence.

        >>> psequence([1,2,3,4]).reverse()
        psequence([4, 3, 2, 1])
        """

    @abstractmethod
    def tolist(self):
        """
        `O(n)`. Convert the sequence to a `list`.

        >>> psequence([1,2,3,4]).tolist()
        [1, 2, 3, 4]
        """

    @abstractmethod
    def totuple(self):
        """
        `O(n)`. Convert the sequence to a `tuple`.

        >>> psequence([1,2,3,4]).totuple()
        (1, 2, 3, 4)
        """

    @abstractmethod
    def transform(self, transformations):
        """
        Apply one or more transformations.

        >>> from pyrsistent import ny
        >>> psequence([1,2,3,4]).transform([ny], lambda x: x*2)
        psequence([2, 4, 6, 8])
        """

    @abstractmethod
    def evolver(self):
        """
        Create an evolver for psequence.

        The evolver acts as a mutable view of the sequence with "transaction
        like" semantics. No part of the underlying sequence is updated, it is
        still fully immutable. Furthermore multiple evolvers created from the
        same psequence do not interfere with each other.

        You may want to use an evolver instead of working directly with the
        psequence in the following cases:

            - Multiple updates are done to the same sequence and the
              intermediate results are of no interest. In this case using an
              evolver may be easier to work with.
            - You need to pass a sequence into a legacy function or a function
              that you have no control over which performs in place mutations
              of lists. In this case pass an evolver instance instead and then
              create a new psequence from the evolver once the function returns.

        The following example illustrates a typical workflow when working with
        evolvers:

        Create the evolver and perform various mutating updates to it:

        >>> seq1 = psequence([1,2,3,4,5])
        >>> evo1 = seq1.evolver()
        >>> evo1[1] = 22
        >>> _ = evo1.append(6)
        >>> _ = evo1.extend([7,8,9])
        >>> evo1[8] += 1
        >>> evo1
        psequence([1, 22, 3, 4, 5, 6, 7, 8, 10]).evolver()

        The underlying psequence remains the same:

        >>> seq1
        psequence([1, 2, 3, 4, 5])

        The changes are kept in the evolver. An updated psequence can be
        created using the persistent() function on the evolver.

        >>> seq2 = evo1.persistent()
        >>> seq2
        psequence([1, 22, 3, 4, 5, 6, 7, 8, 10])

        The new psequence will share data with the original psequence in the
        same way that would have been done if only using operations on the
        psequence.

        >>> evo = psequence([1,2,3,4]).evolver()
        >>> evo[2] = 0
        >>> evo
        psequence([1, 2, 0, 4]).evolver()
        """

    @abstractmethod
    def sort(self, *args, **kwargs):
        """
        `O(nlog(n))`. Created a sorted copy of the sequence.

        Args are the same as `list.sort`.

        >>> psequence([3,1,4,2]).sort()
        psequence([1, 2, 3, 4])
        """

class PSequenceEvolverBase(PSequenceBase):
    """
    Evolver for PSequence.
    """

    @abstractmethod
    def popleft(self):
        """
        `O(1)`. Remove the leftmost element.

        >>> seq = psequence([1,2,3,4]).evolver()
        >>> seq.popleft()
        1
        >>> seq
        psequence([2, 3, 4]).evolver()
        >>> psequence([]).evolver().popleft()
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def popright(self):
        """
        `O(1)`. Remove the rightmost element.

        >>> seq = psequence([1,2,3,4]).evolver()
        >>> seq.popright()
        4
        >>> seq
        psequence([1, 2, 3]).evolver()
        >>> psequence([]).evolver().popright()
        Traceback (most recent call last):
        ...
        IndexError: ...
        """

    @abstractmethod
    def pop(self, index=None):
        """
        Remove and return an element at the specified index.

        See `PSequence.delete` and `list.pop`.

        >>> seq = psequence([1,2,3,4]).evolver()
        >>> seq.pop()
        4
        >>> seq
        psequence([1, 2, 3]).evolver()
        >>> seq.pop(1)
        2
        >>> seq
        psequence([1, 3]).evolver()
        """

    @abstractmethod
    def copy(self):
        """
        `O(1)`. Return a shallow copy of the sequence.

        >>> seq1 = psequence([1,2,3,4]).evolver()
        >>> seq2 = seq1.copy()
        >>> seq2[1] = 0
        >>> seq2
        psequence([1, 0, 3, 4]).evolver()
        >>> seq1
        psequence([1, 2, 3, 4]).evolver()
        """

    @abstractmethod
    def clear(self):
        """
        `O(1)`. Remove all items from the sequence.

        >>> seq = psequence([1,2,3,4]).evolver()
        >>> seq.clear()
        >>> seq
        psequence([]).evolver()
        """

    @abstractmethod
    def persistent(self):
        """
        `O(1)`. Extract the sequence from the evolver.

        >>> seq = psequence([1,2,3,4])
        >>> seq.evolver().persistent()
        psequence([1, 2, 3, 4])
        """

# for doctest
def psequence(*args, **kwargs): # pragma: no cover
    from pyrsistent import psequence as pseq
    return pseq(*args, **kwargs)

__all__ = ('PSequenceBase', 'PSequenceEvolverBase')
