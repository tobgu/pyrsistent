from six import string_types


# enum compat
try:
    from enum import Enum
except:
    class Enum(object): pass
    # no objects will be instances of this class
