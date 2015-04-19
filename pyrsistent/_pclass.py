from pyrsistent import InvariantException
import six
from pyrsistent._field_common import _set_fields, _check_type


class _PClassMeta(type):
    def __new__(mcs, name, bases, dct):
        _set_fields(dct, bases, name='_pclass_fields')
        dct['__slots__'] = ('_pclass_frozen',) + tuple(key for key in dct['_pclass_fields'])
        return super(_PClassMeta, mcs).__new__(mcs, name, bases, dct)

_MISSING_VALUE = object()


@six.add_metaclass(_PClassMeta)
class PClass(object):
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

        for key in self.__slots__:
            if key not in kwargs and key != '_pclass_frozen':
                value = getattr(self, key, _MISSING_VALUE)
                if value is not _MISSING_VALUE:
                    kwargs[key] = value

        return self.__class__(**kwargs)

    def __setattr__(self, key, value):
        if getattr(self, '_pclass_frozen', False):
            raise AttributeError("Can't set attribute, key={0}, value={1}".format(key, value))

        super(PClass, self).__setattr__(key, value)

    def __delattr__(self, key):
            raise AttributeError("Can't delete attribute, key={0}".format(key))
