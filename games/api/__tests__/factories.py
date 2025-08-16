from django.contrib.auth.models import User

import factory

from ...models import Game, GameOnPlatform, Platform, Vendor


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    is_staff = True
    is_active = True


class PlatformFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Platform

    name = factory.Sequence(lambda n: f"Platform {n}")


class VendorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Vendor

    name = factory.Sequence(lambda n: f"Vendor {n}")


class GameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Game

    title = factory.Sequence(lambda n: f"Game {n}")
    play_priority = factory.Faker("random_int", min=1, max=10)
    played = factory.Faker("boolean")
    controller_support = factory.Faker("boolean")
    max_players = factory.Faker("random_int", min=1, max=8)
    party_fit = factory.Faker("boolean")
    review = factory.Faker("random_int", min=1, max=10)
    notes = factory.Faker("text", max_nb_chars=100)


class GameOnPlatformFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GameOnPlatform

    game = factory.SubFactory(GameFactory)
    platform = factory.SubFactory(PlatformFactory)
    source = factory.SubFactory(VendorFactory)
    added = factory.Faker("date_this_year")
    price = factory.Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
