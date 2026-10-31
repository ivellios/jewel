"""Factory definitions for boardgames models."""

import factory

from ..models import BGGExpansion, BGGMetadata, BGGSyncRun, BGGSyncRunStatus


class BGGMetadataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BGGMetadata

    bgg_id = factory.Sequence(lambda n: 100000 + n)
    name = factory.Faker("sentence", max_nb_chars=200)
    yearpublished = factory.Faker("year", min_year=1980, max_year=2030)
    minplayers = factory.Faker("random_int", min=1, max=10)
    maxplayers = factory.Faker("random_int", min=1, max=12)
    playingtime = factory.Faker("random_int", min=10, max=480)


class BGGSyncRunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BGGSyncRun

    status = BGGSyncRunStatus.FULL
    fetch_successful = True
    items_total = factory.Faker("random_int", min=0, max=5000)
    items_fetched = factory.Faker("random_int", min=0, max=5000)
    items_failed = 0
    diagnostics = factory.Faker("sentence", max_nb_chars=500)


class BGGExpansionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BGGExpansion

    expansion = factory.SubFactory(BGGMetadataFactory)
    parent = factory.SubFactory(BGGMetadataFactory)
    exp_type = "boardgameexpansion"
    order = 0
