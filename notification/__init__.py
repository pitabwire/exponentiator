import abc


class NotifierInterface(metaclass=abc.ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'setup') and
                callable(subclass.setup) and
                hasattr(subclass, 'send') and
                callable(subclass.send) or
                NotImplemented)

    @abc.abstractmethod
    def setup(self):
        """Load in the data set"""
        raise NotImplementedError

    @abc.abstractmethod
    def send(self, subject: str, content: str):
        """Extract text from the data set"""
        raise NotImplementedError
