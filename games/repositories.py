import uuid

from abstract.games import GameInterface, GameOnPlatformInterface
from abstract.repositories import GameRepository
from games.models import Game, GameOnPlatform, Genre, Platform, Vendor


class DjangoGameRepository(GameRepository):
    @staticmethod
    def create_game_on_platforms(
        game_model: Game, platforms: list[GameOnPlatformInterface]
    ):
        for platform_game in platforms:
            platform_model, created = Platform.objects.get_or_create(
                name=platform_game.platform.name
            )
            gop, _ = GameOnPlatform.objects.get_or_create(
                platform=platform_model,
                game=game_model,
                added=platform_game.added,
                price=platform_game.price,
                identifier=platform_game.identifier,
            )
            if platform_game.source:
                DjangoGameRepository.create_source(gop, platform_game.source)

    @staticmethod
    def create_genres(game_model: Game, genres: list[str]):
        for genre in genres:
            if genre:
                genre_model, created = Genre.objects.get_or_create(name=genre)
                if not game_model.genres.filter(id=genre_model.id).exists() or created:
                    game_model.genres.add(genre_model)

    @staticmethod
    def create_source(game_on_platform_model: GameOnPlatform, source: str):
        vendor, created = Vendor.objects.get_or_create(name=source)
        if (
            not game_on_platform_model.source
            or game_on_platform_model.source.pk != vendor.pk
            or created
        ):
            game_on_platform_model.source = vendor
            game_on_platform_model.save(update_fields=["source"])

    @staticmethod
    def create_game_model(game: GameInterface, data: dict) -> tuple[Game, bool]:
        if game.id:
            game_model = Game.objects.get(pk=game.id)
            created = False
        else:
            data.pop("id")
            game_model, created = Game.objects.get_or_create(name=game.name)

        for field in data:
            if hasattr(game_model, field):
                value = data.get(field)
                field_value = getattr(game_model, field)
                if value is not None and value != field_value:
                    if field == "notes" and field_value:
                        value += "\n\n" + field_value
                    setattr(game_model, field, value)

        game_model.save(update_fields=list(data.keys()))
        return game_model, created

    @staticmethod
    def game_to_dict(game: GameInterface) -> dict:
        data = game.to_dict()

        # remove complex fields from the dict -- they are being used separately
        data.pop("platforms")
        data.pop("genres")

        return data

    @staticmethod
    def create(game: GameInterface) -> Game:
        data = DjangoGameRepository.game_to_dict(game)

        game_model, created = DjangoGameRepository.create_game_model(game, data)

        if game.genres:
            DjangoGameRepository.create_genres(game_model, game.genres)
        if game.platforms:
            DjangoGameRepository.create_game_on_platforms(game_model, game.platforms)

        game_model.refresh_from_db()
        return game_model, created

    @staticmethod
    def remove(identifier: uuid.uuid4):
        try:
            game = Game.objects.get(id=identifier)
            game.delete()
        except Game.DoesNotExist as err:
            raise ValueError("No game with this ID") from err
