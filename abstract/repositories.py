import abc
import uuid

from abstract.games import GameInterface


class GameRepository(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def create(game: GameInterface):
        pass

    @staticmethod
    @abc.abstractmethod
    def remove(identifier: uuid.uuid4):
        pass
