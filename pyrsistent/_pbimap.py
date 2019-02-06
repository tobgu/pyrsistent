"""An implementation of a bidirectional 1:1 mapping structure.

Provides bijective mappings on pairs in O(log(n)) time, while protecting the bijection property.

"""

from pyrsistent import pmap


class PBiMap():
  """An immutable, left biased, bijection.

  Maps any given key to exactly one value, and enforces that each value has only one key.

  `.set("a", "b")` is said to associate `"a"` to `"b"` on the left side, and `"b"` to `"a"` on the
  right side.

  For the purposes of :py:method`PBiMap.keys()`, :py:method:`PBiMap.values()`,
  :py:method:`PBiMap.items()` and :py:func:`iter()`, this data structure is left-biased. That is, it
  acts as if it were `dict` having only the left-side mappings.

  A `PBiMap` with flipped sides can be produced by calling :py:method:`PBiMap.invert()`.

  .. warning::
     :py:func:`bimap()` is the public interface.

     `PBiMap()` should not be directly called and does not check preconditions.

  """

  def __init__(self, left=None, right=None):
    self.__left__ = pmap(left)
    self.__right__ = pmap(right)

  def __repr__(self):
    return "<PBiMap {{{}}}>".format(", ".join("{} <-> {}".format(k, v)
                                             for k, v in self.__left__.items()))

  def __contains__(self, k):
    return k in self.__left__ or k in self.__right__

  def keys(self):
    """Return an iterable over the (left) keys of the :py:class:`PBiMap`."""

    return self.__left__.keys()

  def values(self):
    """Return an iterable over the (left) values of the :py:class:`PBiMap`."""

    return self.__left__.values()

  def items(self):
    """Return an iterable over the (left) k/v tuples of the :py:class:`PBiMap`."""

    return self.__left__.items()

  def __iter__(self):
    return iter(self.__left__)

  def items(self):
    return self.__left__.items()

  def invert(self):
    """Produce a `PBiMap` with reversed "sidedness".

    Eg. `.keys()` and `.values()` will swap. All tuples of `.items()` will flip, etc.

    """

    return PBiMap(left=self.__right__, right=self.__left__)

  def get(self, k, default=None):
    """Get a value from either the right or left side for the given key."""

    return self.__left__.get(k, None) or self.__right__.get(k, None) or default

  __getitem__ = get

  __call__ = get

  def remove(self, a):
    """Returns a new `PBiMap` with any mappings from or to `a` removed.

    `a` NEED NOT have mappings.

    """

    return self.evolver().remove(a).persistent()

  discard = remove

  def set(self, a, b):
    """Produce a new `PBiMap` with the l-mapping `{a: b}` and the r-mapping `{b: a}`.

    Other mappings from or to both a and b will be removed.

    Returns a new updated `PBiMap`.

    """

    return self.evolver().set(a, b).persistent()

  # FIXME (arrdem 2019-02-04): Does not participate in the `.update()` / `.update_with()` protocol
  # yet because these are poorly defined over a property preserving bijective structure.

  def evolver(self):
    """Return a :py:class:`PBiMap` evolver.

    Evolvers are mutable transformers which can be more efficiently updated many times than an
    immutable structure and can be converted back to a `PBiMap` by calling `.persistent()`.

    """

    return self._Evolver(self)

  class _Evolver():
    def __init__(self, original):
      self.__is_dirty__ = False
      self.__original__ = original
      self.__left_evolver__ = original.__left__.evolver()
      self.__right_evolver__ = original.__right__.evolver()

    def persistent(self):
      """Return a `PBiMap` reflecting any transformations done to this evolver."""

      if self.__is_dirty__:
        return PBiMap(left=self.__left_evolver__.persistent(),
                     right=self.__right_evolver__.persistent())
      else:
        return self.__original__

    def __contains__(self, k):
      return k in self.__left_evolver__ or k in self.__right_evolver__

    def get(self, k, default=None):
      if k in self.__left_evolver__:
        return self.__left_evolver__[k]
      elif k in self.__right_evolver__:
        return self.__right_evolver__[k]
      else:
        return default

    __getitem__ = get

    __call__ = get

    def keys(self):
      return self.__left_evolver__.keys()

    def values(self):
      return self.__left_evolver__.values()

    def __iter__(self):
      return iter(self.__left_evolver__)

    def items(self):
      return self.__left_evolver__.items()

    def invert(self):
      l = self.__right_evolver__
      r = self.__left_evolver__
      self.__left_evolver__ = l
      self.__right_evolver__ = r
      self.__is_dirty__ |= True
      return self

    def remove(self, a):
      # This is obnoxious, but we want to maintain the mapping invariant for which there are 2x2
      # cases. We want to delete any mappings from or to both a and b.

      if a in self.__left_evolver__:
        x = self.__left_evolver__[a]
        self.__left_evolver__.remove(a)
        self.__right_evolver__.remove(x)
        self.__is_dirty__ |= True
        return self

      elif a in self.__right_evolver__:
        x = self.__right_evolver__[a]
        self.__right_evolver__.remove(a)
        self.__left_evolver__.remove(x)
        self.__is_dirty__ |= True
        return self

      else:
        return self

    def set(self, a, b):
      self = self.remove(a)
      self = self.remove(b)
      self.__left_evolver__.set(a, b)
      self.__right_evolver__.set(b, a)
      self.__is_dirty__ |= True
      return self


def pbimap(values=None):
  """Given a mapping (or sequence of [a, b] tuples) return a :py:class:`PBiMap` thereof.

  This constructor enforces the a <-> b invariant.  It is undefined to pass a literal mapping with
  re-occurring RHS values.

  """

  if isinstance(values, dict):
    # Values must be unique.
    # Key uniqueness is provided by dict.
    assert len(set(values.values())) == len(values.values())
  else:
    values = values or {}

  m = PBiMap(left={}, right={}).evolver()

  for a, b in values.items():
    m = m.set(a, b)

  return m.persistent()


bm = pbimap
