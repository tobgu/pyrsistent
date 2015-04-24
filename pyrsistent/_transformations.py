import re
import six


def inc(x):
    """ Add one to the current value """
    return x + 1


def dec(x):
    """ Subtract one from the current value """
    return x - 1


def discard(evolver, key):
    """ Discard the element and returns a structure without the discarded elements """
    try:
        del evolver[key]
    except KeyError:
        pass


# Matchers
def rex(expr):
    """ Regular expression matcher to use together with transform functions """
    r = re.compile(expr)
    return lambda key: isinstance(key, six.string_types) and r.match(key)


def ny(_):
    """ Matcher that matches any value """
    return True

# Support functions
def _chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]


def transform(structure, transformations):
    r = structure
    for path, command in _chunks(transformations, 2):
        r = _do_to_path(r, path, command)
    return r


def _do_to_path(structure, path, command):
    if not path:
        return command(structure) if callable(command) else command

    kvs = _get_keys_and_values(structure, path[0])
    return _update_structure(structure, kvs, path[1:], command)


def _items(structure):
    try:
        return structure.items()
    except AttributeError:
        # Support wider range of structures by adding a transform_items() or similar?
        return list(enumerate(structure))


def _get(structure, key, default):
    try:
        if hasattr(structure, '__getitem__'):
            return structure[key]

        return getattr(structure, key)

    except (IndexError, KeyError):
        return default


def _get_keys_and_values(structure, key_spec):
    from pyrsistent._pmap import pmap
    if callable(key_spec):
        return [(k, v) for k, v in _items(structure) if key_spec(k)]

    return [(key_spec, _get(structure, key_spec, pmap()))]


def _update_structure(structure, kvs, path, command):
    e = structure.evolver()
    for k, v in kvs:
        if not path and command is discard:
            discard(e, k)
        else:
            result = _do_to_path(v, path, command)
            if result is not v:
                e[k] = result
    return e.persistent()