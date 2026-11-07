"""Factory definitions for boardgames models."""

import factory

from boardgames.bgg import BGGCollectionRecord

from ..models import (
    BGGCollectionObservation,
    BGGExpansion,
    BGGMetadata,
    BGGSyncRun,
    BGGSyncRunStatus,
    BoardGame,
)


def collection_record(
    bgg_id: int = 900000,
    owned: bool = True,
    rating: int | None = None,
    numplays: int = 0,
    want_to_play: bool = False,
    **extra,
) -> BGGCollectionRecord:
    """Build a collection record with source fields defaulted to absent."""
    return BGGCollectionRecord(
        bgg_id=bgg_id,
        name=None,
        rating=rating,
        numplays=numplays,
        owned=owned,
        prev_owned=False,
        wishlist=False,
        wishlist_priority=None,
        want=False,
        want_to_play=want_to_play,
        want_to_buy=False,
        preordered=False,
        for_trade=False,
        comment=None,
        last_modified=None,
        min_players=None,
        max_players=None,
        playing_time=None,
        min_playing_time=None,
        max_playing_time=None,
        year=None,
        thumbnail=None,
        image=None,
        bgg_rank=None,
        boardgame_rank=None,
        rating_bayes_average=None,
        rating_average=None,
        rating_median=None,
        rating_stddev=None,
        users_rated=None,
        **extra,
    )


class BGGMetadataFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BGGMetadata

    bgg_id = factory.Sequence(lambda n: 100000 + n)
    name = factory.Faker("sentence")
    yearpublished = factory.Faker("year")
    minplayers = factory.Faker("random_int", min=1, max=10)
    maxplayers = factory.Faker("random_int", min=1, max=12)
    playingtime = factory.Faker("random_int", min=10, max=480)
    min_playing_time = factory.Faker("random_int", min=10, max=240)
    max_playing_time = factory.Faker("random_int", min=240, max=480)
    item_type = "boardgame"
    bgg_url = factory.LazyAttribute(
        lambda metadata: f"https://boardgamegeek.com/boardgame/{metadata.bgg_id}"
    )
    alternative_names = factory.LazyFunction(list)
    families = factory.LazyFunction(list)


class BGGSyncRunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BGGSyncRun

    status = BGGSyncRunStatus.FULL
    fetch_successful = True
    items_total = factory.Faker("random_int", min=0, max=5000)
    items_fetched = factory.Faker("random_int", min=0, max=5000)
    items_failed = 0
    diagnostics = factory.Faker("sentence")


class BGGCollectionObservationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BGGCollectionObservation

    metadata = factory.SubFactory(BGGMetadataFactory)
    sync_run = factory.SubFactory(BGGSyncRunFactory)
    quantity = factory.Faker("random_int", min=0, max=10)
    owned = True
    wishlist = False
    numplays = factory.Faker("random_int", min=0, max=100)


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
