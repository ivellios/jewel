from typing import cast
from uuid import UUID

from abstract.games import GameOnPlatformInterface, VideoGameInterface
from abstract.repositories import VideoGameRepository
from games.models import (
    Genre,
    Vendor,
    VideoGame,
    VideoGameOnPlatform,
    VideoGamePlatform,
)


class DjangoGameRepository(VideoGameRepository):
    @staticmethod
    def create_game_on_platforms(
        game_model: VideoGame, platforms: list[GameOnPlatformInterface]
    ):
        for platform_game in platforms:
            platform_model, created = VideoGamePlatform.objects.get_or_create(
                name=platform_game.platform.name
            )
            gop, _ = VideoGameOnPlatform.objects.get_or_create(
                platform=platform_model,
                game=game_model,
                added=platform_game.added,
                price=platform_game.price,
                identifier=platform_game.identifier,
            )
            if platform_game.vendor:
                DjangoGameRepository.create_vendor(gop, platform_game.vendor)

    @staticmethod
    def create_genres(game_model: VideoGame, genres: list[str]):
        for genre in genres:
            if genre:
                genre_model, created = Genre.objects.get_or_create(name=genre)
                if not game_model.genres.filter(id=genre_model.id).exists() or created:
                    game_model.genres.add(genre_model)

    @staticmethod
    def create_vendor(game_on_platform_model: VideoGameOnPlatform, vendor: str):
        vendor_obj, created = Vendor.objects.get_or_create(name=vendor)
        if (
            not game_on_platform_model.vendor
            or game_on_platform_model.vendor.pk != vendor_obj.pk
            or created
        ):
            game_on_platform_model.vendor = vendor_obj
            game_on_platform_model.save(update_fields=["vendor"])

    @staticmethod
    def create_game_model(
        game: VideoGameInterface, data: dict
    ) -> tuple[VideoGame, bool]:
        if game.id:
            game_model = VideoGame.objects.all_with_orphaned().get(pk=game.id)
            created = False
        else:
            data.pop("id")
            game_model, created = VideoGame.objects.all_with_orphaned().get_or_create(
                name=game.name
            )

        for field in data:
            if hasattr(game_model, field):
                value = data.get(field)
                field_value = getattr(game_model, field)
                if value is not None and value != field_value:
                    if field == "notes" and field_value:
                        value += "\n\n" + field_value
                    setattr(game_model, field, value)

        game_model.save(update_fields=list(data.keys()))
        return cast(tuple[VideoGame, bool], (game_model, created))

    @staticmethod
    def game_to_dict(game: VideoGameInterface) -> dict:
        data = game.to_dict()

        # remove complex fields from the dict -- they are being used separately
        data.pop("platforms")
        data.pop("genres")

        return data

    @staticmethod
    def create(game: VideoGameInterface) -> tuple[VideoGame, bool]:
        data = DjangoGameRepository.game_to_dict(game)

        game_model, created = DjangoGameRepository.create_game_model(game, data)

        if game.genres:
            DjangoGameRepository.create_genres(game_model, game.genres)
        if game.platforms:
            DjangoGameRepository.create_game_on_platforms(game_model, game.platforms)

        game_model.refresh_from_db()
        return cast(tuple[VideoGame, bool], (game_model, created))

    @staticmethod
    def remove(identifier: UUID):
        try:
            game = VideoGame.objects.all_with_orphaned().get(id=identifier)
            game.delete()
        except VideoGame.DoesNotExist as err:
            raise ValueError("No game with this ID") from err
