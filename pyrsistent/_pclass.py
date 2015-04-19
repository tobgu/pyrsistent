import six
from pyrsistent._checked_types import InvariantException, CheckedType
from pyrsistent._field_common import _set_fields, _check_type, _PFIELD_NO_INITIAL, serialize
from pyrsistent._transformations import transform


class _PClassMeta(type):
    def __new__(mcs, name, bases, dct):
        _set_fields(dct, bases, name='_pclass_fields')
        dct['__slots__'] = ('_pclass_frozen',) + tuple(key for key in dct['_pclass_fields'])
        return super(_PClassMeta, mcs).__new__(mcs, name, bases, dct)

_MISSING_VALUE = object()


@six.add_metaclass(_PClassMeta)
class PClass(CheckedType):
    def __new__(cls, **kwargs):    # Support *args?
        result = super(PClass, cls).__new__(cls)
        missing_fields = []
        invariant_errors = []
        for name, field in cls._pclass_fields.items():
            if name in kwargs:
                value = field.factory(kwargs[name])
                _check_type(cls, field, name, value)
                is_ok, error_code = field.invariant(value)
                if not is_ok:
                    invariant_errors.append(error_code)
                else:
                    setattr(result, name, value)
                    del kwargs[name]
            elif field.initial is not _PFIELD_NO_INITIAL:
                setattr(result, name, field.initial)
            elif field.mandatory:
                missing_fields.append('{0}.{1}'.format(cls.__name__, name))

        if invariant_errors or missing_fields:
            raise InvariantException(tuple(invariant_errors), tuple(missing_fields), 'Field invariant failed')

        if kwargs:
            raise AttributeError("'{0}' are not among the specified fields for {1}".format(
                ', '.join(kwargs), cls.__name__))

        result._pclass_frozen = True
        return result

    def set(self, *args, **kwargs):
        if args:
            return self.__class__(**{args[0]: args[1]})

        for key in self._pclass_fields:
            if key not in kwargs:
                value = getattr(self, key, _MISSING_VALUE)
                if value is not _MISSING_VALUE:
                    kwargs[key] = value

        return self.__class__(**kwargs)

    @classmethod
    def create(cls, kwargs):
        if isinstance(kwargs, cls):
            return kwargs

        return cls(**kwargs)

    def serialize(self, format=None):
        result = {}
        for name in self._pclass_fields:
            value = getattr(self, name, _MISSING_VALUE)
            if value is not _MISSING_VALUE:
                result[name] = serialize(self._pclass_fields[name].serializer, format, value)

        return result

    def transform(self, *transformations):
        return transform(self, transformations)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            for name in self._pclass_fields:
                if getattr(self, name, _MISSING_VALUE) != getattr(other, name, _MISSING_VALUE):
                    return False

            return True

        return NotImplemented

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        # May want to optimize this by caching the hash somehow
        return hash(tuple((key, getattr(self, key, _MISSING_VALUE)) for key in self._pclass_fields))

    def __setattr__(self, key, value):
        if getattr(self, '_pclass_frozen', False):
            raise AttributeError("Can't set attribute, key={0}, value={1}".format(key, value))

        super(PClass, self).__setattr__(key, value)

    def __delattr__(self, key):
            raise AttributeError("Can't delete attribute, key={0}".format(key))

    def _to_dict(self):
        result = {}
        for key in self._pclass_fields:
            value = getattr(self, key, _MISSING_VALUE)
            if value is not _MISSING_VALUE:
                result[key] = value

        return result

    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__,
                                 ', '.join('{0}={1}'.format(k, repr(v)) for k, v in self._to_dict().items()))

    def evolver(self):
        return _PClassEvolver(self.__class__, self._to_dict())


class _PClassEvolver(object):
    def __init__(self, base_cls, initial_dict):
        self.base_cls = base_cls
        self.data = initial_dict

    def __getitem__(self, item):
        return self.data[item]

    def set(self, key, value):
        self[key] = value

    def __setitem__(self, key, value):
        self.data[key] = value

    def persistent(self):
        return self.base_cls(**self.data)