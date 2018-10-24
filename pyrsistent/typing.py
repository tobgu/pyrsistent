import six


class SubscriptableType(type):
    def __getitem__(self, key):
        return self


@six.add_metaclass(SubscriptableType)
class CheckedPMap(object):
    pass


@six.add_metaclass(SubscriptableType)
class CheckedPSet(object):
    pass


@six.add_metaclass(SubscriptableType)
class CheckedPVector(object):
    pass


@six.add_metaclass(SubscriptableType)
class PBag(object):
    pass


@six.add_metaclass(SubscriptableType)
class PDeque(object):
    pass


@six.add_metaclass(SubscriptableType)
class PList(object):
    pass


@six.add_metaclass(SubscriptableType)
class PMap(object):
    pass


@six.add_metaclass(SubscriptableType)
class PSet(object):
    pass


@six.add_metaclass(SubscriptableType)
class PVector(object):
    pass
