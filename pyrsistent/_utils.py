class SubscriptableType(type):
    def __getitem__(self, key):
        return self
