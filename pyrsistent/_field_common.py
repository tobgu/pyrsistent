from collections import Iterable
from pyrsistent._checked_types import (
    CheckedType, CheckedPSet, CheckedPMap, CheckedPVector,
    optional as optional_type, InvariantException)


def set_fields(dct, bases, name):
    dct[name] = dict(sum([list(b.__dict__.get(name, {}).items()) for b in bases], []))

    for k, v in list(dct.items()):
        if isinstance(v, _PField):
            dct[name][k] = v
            del dct[k]


def set_global_invariants(dct, bases, name):
    dct[name] = [dct['__invariant__']] if '__invariant__' in dct else []
    dct[name] += [b.__dict__['__invariant__'] for b in bases if '__invariant__' in b.__dict__]
    if not all(callable(invariant) for invariant in dct[name]):
        raise TypeError('Global invariants must be callable')


def check_global_invariants(subject, invariants):
        error_codes = tuple(error_code for is_ok, error_code in
                            (invariant(subject) for invariant in invariants) if not is_ok)
        if error_codes:
            raise InvariantException(error_codes, (), 'Global invariant failed')


def serialize(serializer, format, value):
    if isinstance(value, CheckedType) and serializer is PFIELD_NO_SERIALIZER:
        return value.serialize(format)

    return serializer(format, value)


def check_type(destination_cls, field, name, value):
    if field.type and not any(isinstance(value, t) for t in field.type):
        actual_type = type(value)
        message = "Invalid type for field {0}.{1}, was {2}".format(destination_cls.__name__, name, actual_type.__name__)
        raise PTypeError(destination_cls, name, field.type, actual_type, message)


class _PField(object):
    __slots__ = ('type', 'invariant', 'initial', 'mandatory', 'factory', 'serializer')

    def __init__(self, type, invariant, initial, mandatory, factory, serializer):
        self.type = type
        self.invariant = invariant
        self.initial = initial
        self.mandatory = mandatory
        self.factory = factory
        self.serializer = serializer

PFIELD_NO_TYPE = ()
PFIELD_NO_INVARIANT = lambda _: (True, None)
PFIELD_NO_FACTORY = lambda x: x
PFIELD_NO_INITIAL = object()
PFIELD_NO_SERIALIZER = lambda _, value: value


def field(type=PFIELD_NO_TYPE, invariant=PFIELD_NO_INVARIANT, initial=PFIELD_NO_INITIAL,
          mandatory=False, factory=PFIELD_NO_FACTORY, serializer=PFIELD_NO_SERIALIZER):
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
    if factory is PFIELD_NO_FACTORY and len(types) == 1 and issubclass(tuple(types)[0], CheckedType):
        # TODO: Should this option be looked up at execution time rather than at field construction time?
        #       that would allow checking against all the types specified and if none matches the
        #       first
        factory = tuple(types)[0].create

    field = _PField(type=types, invariant=invariant, initial=initial, mandatory=mandatory,
                    factory=factory, serializer=serializer)

    _check_field_parameters(field)

    return field


def _check_field_parameters(field):
    for t in field.type:
        if not isinstance(t, type):
            raise TypeError('Type paramenter expected, not {0}'.format(type(t)))

    if field.initial is not PFIELD_NO_INITIAL and field.type and not any(isinstance(field.initial, t) for t in field.type):
        raise TypeError('Initial has invalid type {0}'.format(type(t)))

    if not callable(field.invariant):
        raise TypeError('Invariant must be callable')

    if not callable(field.factory):
        raise TypeError('Factory must be callable')

    if not callable(field.serializer):
        raise TypeError('Serializer must be callable')


class PTypeError(TypeError):
    """
    Raised when trying to assign a value with a type that doesn't match the declared type.

    Attributes:
    source_class -- The class of the record
    field -- Field name
    expected_types  -- Types allowed for the field
    actual_type -- The non matching type
    """
    def __init__(self, source_class, field, expected_types, actual_type, *args, **kwargs):
        super(PTypeError, self).__init__(*args, **kwargs)
        self.source_class = source_class
        self.field = field
        self.expected_types = expected_types
        self.actual_type = actual_type


def _sequence_field(checked_class, suffix, item_type, optional, initial):
    """
    Create checked field for either ``PSet`` or ``PVector``.

    :param checked_class: ``CheckedPSet`` or ``CheckedPVector``.
    :param suffix: Suffix for new type name.
    :param item_type: The required type for the items in the set.
    :param bool optional: If true, ``None`` can be used as a value for
        this field.
    :param initial: Initial value to pass to factory.

    :return: A ``field`` containing a checked class.
    """
    class TheType(checked_class):
        __type__ = item_type
    TheType.__name__ = item_type.__name__.capitalize() + suffix

    if optional:
        def factory(argument):
            if argument is None:
                return None
            else:
                return TheType.create(argument)
    else:
        factory = TheType.create

    return field(type=optional_type(TheType) if optional else TheType,
                 factory=factory, mandatory=True,
                 initial=factory(initial))


def pset_field(item_type, optional=False, initial=()):
    """
    Create checked ``PSet`` field.

    :param item_type: The required type for the items in the set.
    :param bool optional: If true, ``None`` can be used as a value for
        this field.
    :param initial: Initial value to pass to factory if no value is given
        for the field.

    :return: A ``field`` containing a ``CheckedPSet`` of the given type.
    """
    return _sequence_field(CheckedPSet, "PSet", item_type, optional,
                           initial)


def pvector_field(item_type, optional=False, initial=()):
    """
    Create checked ``PVector`` field.

    :param item_type: The required type for the items in the vector.
    :param bool optional: If true, ``None`` can be used as a value for
        this field.
    :param initial: Initial value to pass to factory if no value is given
        for the field.

    :return: A ``field`` containing a ``CheckedPVector`` of the given type.
    """
    return _sequence_field(CheckedPVector, "PVector", item_type, optional,
                           initial)


_valid = lambda item: (True, "")


def pmap_field(key_type, value_type, optional=False, invariant=PFIELD_NO_INVARIANT):
    """
    Create a checked ``PMap`` field.

    :param key: The required type for the keys of the map.
    :param value: The required type for the values of the map.
    :param bool optional: If true, ``None`` can be used as a value for
        this field.
    :param invariant: Pass-through to ``field``.

    :return: A ``field`` containing a ``CheckedPMap``.
    """
    class TheMap(CheckedPMap):
        __key_type__ = key_type
        __value_type__ = value_type
    TheMap.__name__ = (key_type.__name__.capitalize() +
                       value_type.__name__.capitalize() + "PMap")

    if optional:
        def factory(argument):
            if argument is None:
                return None
            else:
                return TheMap.create(argument)
    else:
        factory = TheMap.create

    return field(mandatory=True, initial=TheMap(),
                 type=optional_type(TheMap) if optional else TheMap,
                 factory=factory, invariant=invariant)
