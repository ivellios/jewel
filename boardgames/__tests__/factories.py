"""Factory definitions for boardgames models."""

import factory

from ..models import BGGExpansion, BGGMetadata, BGGSyncRun, BGGSyncRunStatus, BoardGame


class BGGMetadataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BGGMetadata

    bgg_id = factory.Sequence(lambda n: 100000 + n)
    name = factory.Faker("sentence")
    yearpublished = factory.Faker("year")
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
    diagnostics = factory.Faker("sentence")


class BGGExpansionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BGGExpansion

    expansion = factory.SubFactory(BGGMetadataFactory)
    parent = factory.SubFactory(BGGMetadataFactory)
    exp_type = "boardgameexpansion"
    order = 0


class BoardGameFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BoardGame

    metadata = factory.SubFactory(BGGMetadataFactory)
    language = "en"
    edition_label = factory.Faker("word")
    name = factory.Faker("sentence")
    condition = "mint"
    storage = factory.Faker("word")
    purchase_date = factory.Faker("date_object")
    imported = False
    owned = False
    removed = False
