import six
from pyrsistent._precord import set_fields


class _PClassMeta(type):
    def __new__(mcs, name, bases, dct):
        set_fields(dct, bases, name='_pclass_fields')
        dct['__slots__'] = ('_pclass_frozen',) + tuple(key for key in dct['_pclass_fields'])
        return super(_PClassMeta, mcs).__new__(mcs, name, bases, dct)

_MISSING_VALUE = object()

@six.add_metaclass(_PClassMeta)
class PClass(object):
    def __new__(cls, *args, **kwargs):
        result = super(PClass, cls).__new__(cls)
        for k, v in kwargs.items():
            if k != '_pclass_frozen':
                setattr(result, k, v)

        result._pclass_frozen = True
        return result

    def set(self, *args, **kwargs):
        new_values = {}
        for key in self.__slots__:
            value = getattr(self, key, _MISSING_VALUE)
            if value is not _MISSING_VALUE:
                new_values[key] = value

        new_values.update(kwargs)
        return self.__class__(**new_values)

    def __setattr__(self, key, value):
        if getattr(self, '_pclass_frozen', False):
            raise AttributeError("Can't set attribute, key={}, value={}".format(key, value))

        super(PClass, self).__setattr__(key, value)

    def __delattr__(self, key):
            raise AttributeError("Can't delete attribute, key={}".format(key))
