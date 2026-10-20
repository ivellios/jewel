from django.contrib.auth.models import User

import factory

from ...models import Vendor, VideoGame, VideoGameOnPlatform, VideoGamePlatform


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    is_staff = True
    is_active = True


class VideoGamePlatformFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VideoGamePlatform

    name = factory.Sequence(lambda n: f"Platform {n}")


class VendorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Vendor

    name = factory.Sequence(lambda n: f"Vendor {n}")


class VideoGameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VideoGame

    name = factory.Sequence(lambda n: f"Game {n}")
    play_priority = factory.Faker("random_int", min=1, max=10)
    played = factory.Faker("boolean")
    controller_support = factory.Faker("boolean")
    max_players = factory.Faker("random_int", min=1, max=8)
    party_fit = factory.Faker("boolean")
    review = factory.Faker("random_int", min=1, max=10)
    notes = factory.Faker("text", max_nb_chars=100)

    @factory.post_generation
    def platforms(self, create, extracted, **kwargs):
        if not create:
            return

        # Create a default platform relationship so game is not orphaned
        # unless explicitly told not to (platforms=False)
        if extracted is None:
            platform = VideoGamePlatformFactory()
            VideoGameOnPlatform.objects.create(game=self, platform=platform)


class VideoGameOnPlatformFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VideoGameOnPlatform

    game = factory.SubFactory(VideoGameFactory)
    platform = factory.SubFactory(VideoGamePlatformFactory)
    vendor = factory.SubFactory(VendorFactory)
    added = factory.Faker("date_this_year")
    price = factory.Faker("pydecimal", left_digits=2, right_digits=2, positive=True)
