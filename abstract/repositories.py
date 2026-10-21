import abc
from uuid import UUID

from abstract.games import VideoGameInterface


class VideoGameRepository(abc.ABC):
    @staticmethod
    @abc.abstractmethod
    def create(game: VideoGameInterface):
        pass

    @staticmethod
    @abc.abstractmethod
    def remove(identifier: UUID):
        pass
