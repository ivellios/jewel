import abc


class ImporterInterface(abc.ABC):
    @abc.abstractmethod
    def process(self, data):
        pass


class GamesImporter(ImporterInterface):
    pass
