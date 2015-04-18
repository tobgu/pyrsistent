from collections import Iterable
import six
from pyrsistent._checked_types import CheckedType, _restore_pickle, InvariantException
from pyrsistent._pmap import PMap, pmap


class _PRecordMeta(type):
    def __new__(mcs, name, bases, dct):
        dct['_precord_fields'] = dict(sum([list(b.__dict__.get('_precord_fields', {}).items()) for b in bases], []))

        for k, v in list(dct.items()):
            if isinstance(v, _PRecordField):
                dct['_precord_fields'][k] = v
                del dct[k]

        # Global invariants are inherited
        dct['_precord_invariants'] = [dct['__invariant__']] if '__invariant__' in dct else []
        dct['_precord_invariants'] += [b.__dict__['__invariant__'] for b in bases if '__invariant__' in b.__dict__]
        if not all(callable(invariant) for invariant in dct['_precord_invariants']):
            raise TypeError('Global invariants must be callable')

        dct['_precord_mandatory_fields'] = \
            set(name for name, field in dct['_precord_fields'].items() if field.mandatory)

        dct['_precord_initial_values'] = \
            dict((k, field.initial) for k, field in dct['_precord_fields'].items() if field.initial is not _PRECORD_NO_INITIAL)

        dct['__slots__'] = ()

        return super(_PRecordMeta, mcs).__new__(mcs, name, bases, dct)




class _PRecordField(object):
    __slots__ = ('type', 'invariant', 'initial', 'mandatory', 'factory', 'serializer')

    def __init__(self, type, invariant, initial, mandatory, factory, serializer):
        self.type = type
        self.invariant = invariant
        self.initial = initial
        self.mandatory = mandatory
        self.factory = factory
        self.serializer = serializer

_PRECORD_NO_TYPE = ()
_PRECORD_NO_INVARIANT = lambda _: (True, None)
_PRECORD_NO_FACTORY = lambda x: x
_PRECORD_NO_INITIAL = object()
_PRECORD_NO_SERIALIZER = lambda _, value: value

def field(type=_PRECORD_NO_TYPE, invariant=_PRECORD_NO_INVARIANT, initial=_PRECORD_NO_INITIAL,
          mandatory=False, factory=_PRECORD_NO_FACTORY, serializer=_PRECORD_NO_SERIALIZER):
    """
    Field specification factory for :py:class:`PRecord`.

    :param type: a type or iterable with types that are allowed for this field
    :param invariant: a function specifying an invariant that must hold for the field
    :param initial: value of field if not specified when instantiating the record
    :param mandatorty: boolean specifying if the field is mandatory or not
    :param factory: function called when field is set.
    :param serializer: function that returns a serialized version of the field
    """

    types = set(type) if isinstance(type, Iterable) else set([type])

    # If no factory is specified and the type is another CheckedType use the factory method of that CheckedType
    if factory is _PRECORD_NO_FACTORY and len(types) == 1 and issubclass(tuple(types)[0], CheckedType):
        # TODO: Should this option be looked up at execution time rather than at field construction time?
        #       that would allow checking against all the types specified and if none matches the
        #       first
        factory = tuple(types)[0].create

    field = _PRecordField(type=types, invariant=invariant, initial=initial, mandatory=mandatory,
                          factory=factory, serializer=serializer)

    _check_field_parameters(field)

    return field


def _check_field_parameters(field):
    for t in field.type:
        if not isinstance(t, type):
            raise TypeError('Type paramenter expected, not {0}'.format(type(t)))

    if field.initial is not _PRECORD_NO_INITIAL and field.type and not any(isinstance(field.initial, t) for t in field.type):
        raise TypeError('Initial has invalid type {0}'.format(type(t)))

    if not callable(field.invariant):
        raise TypeError('Invariant must be callable')

    if not callable(field.factory):
        raise TypeError('Factory must be callable')

    if not callable(field.serializer):
        raise TypeError('Serializer must be callable')


@six.add_metaclass(_PRecordMeta)
class PRecord(PMap, CheckedType):
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
        if '_precord_size' in kwargs and '_precord_buckets' in kwargs:
            return super(PRecord, cls).__new__(cls, kwargs['_precord_size'], kwargs['_precord_buckets'])

        initial_values = kwargs
        if cls._precord_initial_values:
            initial_values = dict(cls._precord_initial_values)
            initial_values.update(kwargs)

        e = _PRecordEvolver(cls, pmap())
        for k, v in initial_values.items():
            e[k] = v

        return e.persistent()

    def set(self, *args, **kwargs):
        """
        Set a field in the record. This set function differs slightly from that in the PMap
        class. First of all it accepts key-value pairs. Second it accepts multiple key-value
        pairs to perform one, atomic, update of multiple fields.
        """

        # The PRecord set() can accept kwargs since all fields that have been declared are
        # valid python identifiers. Also allow multiple fields to be set in one operation.
        if args:
            return super(PRecord, self).set(args[0], args[1])

        return self.update(kwargs)

    def evolver(self):
        """
        Returns an evolver of this object.
        """
        return _PRecordEvolver(self.__class__, self)

    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__,
                                 ', '.join('{0}={1}'.format(k, repr(v)) for k, v in self.items()))

    @classmethod
    def create(cls, kwargs):
        """
        Factory method. Will create a new PRecord of the current type and assign the values
        specified in kwargs.
        """
        if isinstance(kwargs, cls):
            return kwargs

        return cls(**kwargs)

    def __reduce__(self):
        # Pickling support
        return _restore_pickle, (self.__class__, dict(self),)

    def serialize(self, format=None):
        """
        Serialize the current PRecord using custom serializer functions for fields where
        such have been supplied.
        """
        def _serialize(k, v):
            serializer = self.__class__._precord_fields[k].serializer
            if isinstance(v, CheckedType) and serializer is _PRECORD_NO_SERIALIZER:
                return v.serialize(format)

            return serializer(format, v)

        return dict((k, _serialize(k, v)) for k, v in self.items())


class PRecordTypeError(TypeError):
    """
    Raised when trying to assign a value with a type that doesn't match the declared type.

    Attributes:
    source_class -- The class of the record
    field -- Field name
    expected_types  -- Types allowed for the field
    actual_type -- The non matching type
    """
    def __init__(self, source_class, field, expected_types, actual_type, *args, **kwargs):
        super(PRecordTypeError, self).__init__(*args, **kwargs)
        self.source_class = source_class
        self.field = field
        self.expected_types = expected_types
        self.actual_type = actual_type


class _PRecordEvolver(PMap._Evolver):
    __slots__ = ('_destination_cls', '_invariant_error_codes', '_missing_fields')

    def __init__(self, cls, *args):
        super(_PRecordEvolver, self).__init__(*args)
        self._destination_cls = cls
        self._invariant_error_codes = []
        self._missing_fields = []

    def __setitem__(self, key, original_value):
        self.set(key, original_value)

    def set(self, key, original_value):
        field = self._destination_cls._precord_fields.get(key)
        if field:
            try:
                value = field.factory(original_value)
            except InvariantException as e:
                self._invariant_error_codes += e.invariant_errors
                self._missing_fields += e.missing_fields
                return self

            if field.type and not any(isinstance(value, t) for t in field.type):
                actual_type = type(value)
                message = "Invalid type for field {0}.{1}, was {2}".format(self._destination_cls.__name__, key, actual_type.__name__)
                raise PRecordTypeError(self._destination_cls, key, field.type, actual_type, message)

            is_ok, error_code = field.invariant(value)
            if not is_ok:
                self._invariant_error_codes.append(error_code)

            return super(_PRecordEvolver, self).set(key, value)
        else:
            raise AttributeError("'{0}' is not among the specified fields for {1}".format(key, self._destination_cls.__name__))

    def persistent(self):
        cls = self._destination_cls
        is_dirty = self.is_dirty()
        pm = super(_PRecordEvolver, self).persistent()
        if is_dirty or not isinstance(pm, cls):
            result = cls(_precord_buckets=pm._buckets, _precord_size=pm._size)
        else:
            result = pm

        if cls._precord_mandatory_fields:
            self._missing_fields += tuple('{0}.{1}'.format(cls.__name__, f) for f
                                          in (cls._precord_mandatory_fields - set(result.keys())))

        if self._invariant_error_codes or self._missing_fields:
            raise InvariantException(tuple(self._invariant_error_codes), tuple(self._missing_fields),
                                     'Field invariant failed')

        error_codes = tuple(error_code for is_ok, error_code in
                            (invariant(result) for invariant in cls._precord_invariants) if not is_ok)
        if error_codes:
            raise InvariantException(error_codes, (), 'Global invariant failed')

        return result

