from typing import Any
from pyrsistent._checked_types import CheckedType, _restore_pickle, InvariantException, store_invariants
from pyrsistent._field_common import (
    set_fields, check_type, is_field_ignore_extra_complaint, PFIELD_NO_INITIAL, serialize, check_global_invariants
)
from pyrsistent._pmap import PMap, pmap


class _PRecordMeta(type):
    def __new__(mcs, name, bases, dct):
        set_fields(dct, bases, name='_precord_fields')
        store_invariants(dct, bases, '_precord_invariants', '__invariant__')

        dct['_precord_mandatory_fields'] = \
            set(name for name, field in dct['_precord_fields'].items() if field.mandatory)

        dct['_precord_initial_values'] = \
            dict((k, field.initial) for k, field in dct['_precord_fields'].items()
                 if field.initial is not PFIELD_NO_INITIAL)

        dct['__slots__'] = ()

        return super(_PRecordMeta, mcs).__new__(mcs, name, bases, dct)


class PRecord(PMap[str, Any], CheckedType, metaclass=_PRecordMeta):
    """
    A PRecord is a PMap with a fixed set of specified fields. Records are declared as python classes inheriting
    from PRecord. Because it is a PMap it has full support for all Mapping methods such as iteration and element
    access using subscript notation.

    More documentation and examples of PRecord usage is available at https://github.com/tobgu/pyrsistent
    """
    def __new__(cls, **kwargs):
        # Hack total! If these two special attributes exist that means we can create
        # ourselves. Otherwise we need to go through the Evolver to create the structures
        # for us.
        if '_precord_size' in cls.__dict__ and '_precord_buckets' in cls.__dict__:
            return super(PRecord, cls).__new__(cls, cls._precord_size, cls._precord_buckets)

        factory_fields = cls._precord_fields
        initial_dict = cls._precord_initial_values.copy()
        initial_dict.update(kwargs)

        e = _PRecordEvolver(cls, pmap(), factory_fields)
        for k, v in initial_dict.items():
            e[k] = v

        return e.persistent()

    def set(self, key, val):
        if key not in self._precord_fields:
            raise AttributeError("PRecord does not have field '{0}'".format(key))

        return self.evolver().set(key, val).persistent()

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError("PRecord does not have field '{0}'".format(key))

    def __setattr__(self, key, val):
        # This is mainly here to prevent users from accidentally setting
        # fields on PRecords which will not work properly. The metaclass
        # should prevent this from happening in the first place.
        raise AttributeError("can't set attribute")

    def evolver(self):
        return _PRecordEvolver(self.__class__, self, self._precord_fields)

    def serialize(self, format=None):
        result = {}
        for key, value in self.items():
            result[key] = serialize(self._precord_fields[key].serializer, format, value)

        return result

    def __reduce__(self):
        # Pickling support
        return _restore_pickle, (self.__class__, dict(self),)


class _PRecordEvolver(object):
    __slots__ = ('_destination_cls', '_pmap_evolver', '_invariant_error_codes', '_factory_fields', '_missing_fields')

    def __init__(self, cls, initial_pmap, factory_fields):
        self._destination_cls = cls
        self._pmap_evolver = initial_pmap.evolver()
        self._factory_fields = factory_fields
        self._invariant_error_codes = []
        self._missing_fields = []

    def __setitem__(self, key, original_val):
        self._invariant_error_codes = []
        self._missing_fields = []

        field = self._factory_fields.get(key)
        if field:
            if is_field_ignore_extra_complaint(field, key, self._destination_cls):
                return

            try:
                val = check_type(original_val, field)
            except TypeError as e:
                raise PTypeError(self._destination_cls, field, str(e))

            self._pmap_evolver[key] = val
        elif key not in self._destination_cls._precord_fields:
            raise AttributeError("PRecord does not have field '{0}'".format(key))
        else:
            # This should never happen, but guard against it anyway
            raise AttributeError("Unhandled field '{0}'".format(key))

        return self

    def persistent(self):
        cls = self._destination_cls
        pmap = self._pmap_evolver.persistent()

        if cls._precord_mandatory_fields:
            self._missing_fields = []
            for field in cls._precord_mandatory_fields:
                if field not in pmap:
                    self._missing_fields.append(field)

            if self._missing_fields:
                raise InvariantException(
                    tuple(self._missing_fields),
                    tuple(),
                    'Missing mandatory fields: {0}'.format(tuple(self._missing_fields)))

        check_global_invariants(pmap, cls._precord_invariants, error_code='PRecord')

        if pmap is self._pmap_evolver:
            # This shouldn't really be needed but the evolver promises to return
            # a new map on persistent() so there's a contract to uphold.
            pmap = PMap(pmap._size, pmap._buckets)

        result = cls.__new__(cls)
        result._size = pmap._size
        result._buckets = pmap._buckets

        return result


class PTypeError(TypeError):
    def __init__(self, cls, field, msg):
        super(PTypeError, self).__init__(
            "Type error for field {}.{}: {}".format(cls.__name__, field.name, msg))
