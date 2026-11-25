"""Focused service tests for canonical metadata upsert."""

from django.test import TestCase

from boardgames.bgg import BGGDetailRecord
from boardgames.models import BGGMetadata, BoardGame
from boardgames.services import upsert_detail
from boardgames.services.canonical_upsert import UpsertResult

from ..__tests__.factories import (
    BGGMetadataFactory,
    BoardGameFactory,
)


class UpsertDetailServiceTest(TestCase):
    """Verify upsert_detail core behaviour."""

    def _make_record(
        self,
        bgg_id: int = 500000,
        name: str | None = "Terra Mystica Extended",
        year: int = 2012,
        expansions: tuple[int, ...] = (),
        expands: tuple[int, ...] = (),
        **extra,
    ) -> BGGDetailRecord:
        """Convenience factory for BGGDetailRecord fixtures."""

        return BGGDetailRecord(
            bgg_id=bgg_id,
            name=name,
            year=year,
            min_players=2,
            max_players=4,
            playing_time=120,
            min_playing_time=90,
            max_playing_time=150,
            item_type="boardgame",
            bgg_url=f"https://boardgamegeek.com/boardgame/{bgg_id}",
            designers="Stefan Feld",
            publishers="Clemson University",
            mechanics="Area Influence, Set Collection",
            categories="Farming, Strategy",
            rating_bayes_average=4.12,
            rating_average=4.35,
            rating_median=4.5,
            rating_stddev=0.8,
            rating_num_weights=2.8,
            bgg_rank=4,
            boardgame_rank=4,
            users_rated=45000,
            users_owned=12000,
            thumbnail="https://thumb.example.com/tm.jpg",
            image="https://img.example.com/tm.jpg",
            description="A fantasy civilization game.",
            expansions=expansions,
            expands=expands,
            alternative_names=("Terra Mystica HD", "Terra GM"),
            families=("Engine Building", "Tile Placement"),
            plays_count=9800,
            **extra,
        )

    def test_creates_new_metadata_row(self):
        """A new BGG ID creates one distinct metadata row."""

        record = self._make_record(bgg_id=500001)
        result = upsert_detail(record)

        self.assertIsInstance(result, UpsertResult)
        self.assertIsInstance(result.metadata, BGGMetadata)
        self.assertEqual(result.metadata.bgg_id, 500001)
        self.assertEqual(result.metadata.name, "Terra Mystica Extended")
        self.assertEqual(BGGMetadata.objects.count(), 1)

    def test_returns_mapping_fields(self):
        """All non-None fields map to the correct metadata columns."""

        record = self._make_record(bgg_id=500002)
        result = upsert_detail(record)

        meta = result.metadata
        self.assertEqual(meta.name, "Terra Mystica Extended")
        self.assertEqual(meta.yearpublished, 2012)
        self.assertEqual(meta.minplayers, 2)
        self.assertEqual(meta.maxplayers, 4)
        self.assertEqual(meta.playingtime, 120)
        self.assertEqual(meta.comment, "A fantasy civilization game.")
        self.assertEqual(meta.thumbnail, "https://thumb.example.com/tm.jpg")
        self.assertEqual(meta.image, "https://img.example.com/tm.jpg")
        self.assertEqual(meta.publishers, "Clemson University")
        self.assertEqual(meta.designers, "Stefan Feld")
        self.assertEqual(meta.mechanics, "Area Influence, Set Collection")
        self.assertEqual(meta.categories, "Farming, Strategy")

    def test_returns_mapping_fields_extended(self):
        """Packet 5 fields: ratings, ranks, users, item_type, URLs,
        alternative_names, families, plays_count, min/max playing time."""

        record = self._make_record(bgg_id=500010)
        result = upsert_detail(record)
        meta = result.metadata

        # Item type and source URL.
        self.assertEqual(meta.item_type, "boardgame")
        self.assertEqual(
            meta.bgg_url,
            "https://boardgamegeek.com/boardgame/500010",
        )

        # Min/max playing time.
        self.assertEqual(meta.min_playing_time, 90)
        self.assertEqual(meta.max_playing_time, 150)

        # Ratings.
        self.assertEqual(meta.rating_bayes_average, 4.12)
        self.assertEqual(meta.rating_average, 4.35)
        self.assertEqual(meta.rating_median, 4.5)
        self.assertEqual(meta.rating_stddev, 0.8)
        self.assertEqual(meta.rating_num_weights, 2.8)

        # Ranks and user counts.
        self.assertEqual(meta.bgg_rank, 4)
        self.assertEqual(meta.boardgame_rank, 4)
        self.assertEqual(meta.users_rated, 45000)
        self.assertEqual(meta.users_owned, 12000)

        # Play aggregate.
        self.assertEqual(meta.plays_count, 9800)

        # Alternative names and families (JSON → tuple stored as JSONField).
        self.assertEqual(
            meta.alternative_names,
            ["Terra Mystica HD", "Terra GM"],
        )
        self.assertEqual(
            meta.families,
            ["Engine Building", "Tile Placement"],
        )

    def test_updates_existing_metadata_row(self):
        """Repeated upsert with the same BGG ID updates the existing row."""

        record1 = self._make_record(bgg_id=500003, name="Original Name")
        result1 = upsert_detail(record1)
        original_pk = result1.metadata.pk

        # Update with new data for the same bgg_id.
        record2 = self._make_record(
            bgg_id=500003,
            name="Updated Name",
            year=2020,
        )
        result2 = upsert_detail(record2)

        # Same row, updated fields.
        self.assertEqual(result1.metadata.pk, result2.metadata.pk)
        self.assertEqual(BGGMetadata.objects.count(), 1)

        refreshed = BGGMetadata.objects.get(pk=original_pk)
        self.assertEqual(refreshed.name, "Updated Name")
        self.assertEqual(refreshed.yearpublished, 2020)

    def test_idempotent_repeated_upsert(self):
        """Calling upsert_detail twice with the same record yields one row."""

        record = self._make_record(bgg_id=500004)

        result1 = upsert_detail(record)
        result2 = upsert_detail(record)

        self.assertEqual(BGGMetadata.objects.count(), 1)
        self.assertEqual(result1.metadata.pk, result2.metadata.pk)

    def test_distinct_bggs_create_distinct_rows(self):
        """Distinct BGG IDs produce distinct metadata rows."""

        rec_a = self._make_record(bgg_id=500005, name="Game A")
        rec_b = self._make_record(bgg_id=500006, name="Game B")

        upsert_detail(rec_a)
        upsert_detail(rec_b)

        self.assertEqual(BGGMetadata.objects.count(), 2)
        bgg_ids = list(BGGMetadata.objects.values_list("bgg_id", flat=True))
        self.assertEqual(set(bgg_ids), {500005, 500006})

    def test_omitted_optional_values_do_not_erase(self):
        """When a field is None, the existing DB value is preserved."""

        # Insert a row with full data.
        record_full = self._make_record(bgg_id=500007)
        upsert_detail(record_full)

        # Now upsert with partial data (name=None, most fields missing).
        partial_record = BGGDetailRecord(
            bgg_id=500007,
            name=None,  # explicitly omitted
            year=None,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
            item_type=None,
            bgg_url=None,
            designers=None,
            publishers=None,
            mechanics=None,
            categories=None,
            rating_bayes_average=None,
            rating_average=None,
            rating_median=None,
            rating_stddev=None,
            rating_num_weights=None,
            bgg_rank=None,
            boardgame_rank=None,
            users_rated=None,
            users_owned=None,
            thumbnail=None,
            image=None,
            description=None,
            alternative_names=None,
            families=None,
            plays_count=None,
        )
        upsert_detail(partial_record)

        meta = BGGMetadata.objects.get(bgg_id=500007)
        # Original values must survive.
        self.assertEqual(meta.name, "Terra Mystica Extended")
        self.assertEqual(meta.yearpublished, 2012)
        self.assertEqual(meta.minplayers, 2)
        self.assertEqual(meta.maxplayers, 4)
        self.assertEqual(meta.playingtime, 120)
        self.assertEqual(meta.designers, "Stefan Feld")
        self.assertEqual(meta.categories, "Farming, Strategy")
        self.assertEqual(meta.item_type, "boardgame")
        self.assertEqual(
            meta.bgg_url,
            "https://boardgamegeek.com/boardgame/500007",
        )
        self.assertEqual(meta.min_playing_time, 90)
        self.assertEqual(meta.max_playing_time, 150)
        self.assertEqual(meta.rating_bayes_average, 4.12)
        self.assertEqual(meta.rating_average, 4.35)
        self.assertEqual(meta.rating_median, 4.5)
        self.assertEqual(meta.rating_stddev, 0.8)
        self.assertEqual(meta.rating_num_weights, 2.8)
        self.assertEqual(meta.bgg_rank, 4)
        self.assertEqual(meta.boardgame_rank, 4)
        self.assertEqual(meta.users_rated, 45000)
        self.assertEqual(meta.users_owned, 12000)
        self.assertEqual(meta.plays_count, 9800)
        self.assertEqual(
            meta.alternative_names,
            ["Terra Mystica HD", "Terra GM"],
        )
        self.assertEqual(
            meta.families,
            ["Engine Building", "Tile Placement"],
        )

    def test_empty_record_preserves_all_fields(self):
        """An empty record (only bgg_id) does not erase anything."""

        record_full = self._make_record(bgg_id=500008)
        upsert_detail(record_full)

        empty_record = BGGDetailRecord(
            bgg_id=500008,
            name=None,
            year=None,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
            item_type=None,
            bgg_url=None,
            designers=None,
            publishers=None,
            mechanics=None,
            categories=None,
            rating_bayes_average=None,
            rating_average=None,
            rating_median=None,
            rating_stddev=None,
            rating_num_weights=None,
            bgg_rank=None,
            boardgame_rank=None,
            users_rated=None,
            users_owned=None,
            thumbnail=None,
            image=None,
            description=None,
            alternative_names=None,
            families=None,
            plays_count=None,
        )
        upsert_detail(empty_record)

        meta = BGGMetadata.objects.get(bgg_id=500008)
        self.assertEqual(meta.name, "Terra Mystica Extended")
        self.assertEqual(meta.yearpublished, 2012)
        self.assertEqual(meta.item_type, "boardgame")
        self.assertEqual(meta.plays_count, 9800)


class UpsertBoardGameIndependenceTest(TestCase):
    """Verify that upsert_detail never touches BoardGame copies."""

    def _make_record(
        self,
        bgg_id: int = 700000,
    ) -> BGGDetailRecord:
        return BGGDetailRecord(
            bgg_id=bgg_id,
            name="Independence Test",
            year=2015,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
            item_type=None,
            bgg_url=None,
            designers=None,
            publishers=None,
            mechanics=None,
            categories=None,
            rating_bayes_average=None,
            rating_average=None,
            rating_median=None,
            rating_stddev=None,
            rating_num_weights=None,
            bgg_rank=None,
            boardgame_rank=None,
            users_rated=None,
            users_owned=None,
            thumbnail=None,
            image=None,
            description=None,
            expansions=(),
            expands=(),
            alternative_names=(),
            designers_list=(),
            publishers_list=(),
            mechanics_list=(),
            categories_list=(),
            families=(),
            plays_count=None,
        )

    def _boardgame_count(self) -> int:
        from boardgames.models import BoardGame

        return BoardGame.objects.count()

    def test_upsert_does_not_touch_boardgame_rows(self):
        """Creating / updating metadata does not create BoardGame rows."""

        boardgame_count_before = self._boardgame_count()

        record = self._make_record(bgg_id=700000)
        upsert_detail(record)

        self.assertEqual(self._boardgame_count(), boardgame_count_before)

    def test_upsert_does_not_modify_existing_boardgame(self):
        """Updating metadata does not modify existing BoardGame copies."""

        meta = BGGMetadataFactory(name="Existing Game")
        bg = BoardGameFactory(
            metadata=meta,
            name="Local Copy Name",
            language="pl",
            condition="good",
        )

        # Upsert a different BGG ID that shares the same metadata FK.
        record = self._make_record(bgg_id=meta.bgg_id)
        upsert_detail(record)

        # BoardGame row is unchanged.
        refreshed_bg = BoardGame.objects.get(pk=bg.pk)
        self.assertEqual(refreshed_bg.name, "Local Copy Name")
        self.assertEqual(refreshed_bg.language, "pl")
        self.assertEqual(refreshed_bg.condition, "good")


class NumplayersSummaryUpsertTest(TestCase):
    """Verify numplayers_summary persistence through upsert."""

    def _make_base_record(
        self,
        bgg_id: int = 600010,
        name: str | None = "Terra Mystica Extended",
        year: int = 2012,
        expansions: tuple[int, ...] = (),
        expands: tuple[int, ...] = (),
        **extra,
    ) -> BGGDetailRecord:
        return BGGDetailRecord(
            bgg_id=bgg_id,
            name=name,
            year=year,
            min_players=2,
            max_players=4,
            playing_time=120,
            min_playing_time=90,
            max_playing_time=150,
            item_type="boardgame",
            bgg_url=f"https://boardgamegeek.com/boardgame/{bgg_id}",
            designers="Stefan Feld",
            publishers="Clemson University",
            mechanics="Area Influence, Set Collection",
            categories="Farming, Strategy",
            rating_bayes_average=4.12,
            rating_average=4.35,
            rating_median=4.5,
            rating_stddev=0.8,
            rating_num_weights=2.8,
            bgg_rank=4,
            boardgame_rank=4,
            users_rated=45000,
            users_owned=12000,
            thumbnail="https://thumb.example.com/tm.jpg",
            image="https://img.example.com/tm.jpg",
            description="A fantasy civilization game.",
            expansions=expansions,
            expands=expands,
            alternative_names=("Terra Mystica HD", "Terra GM"),
            families=("Engine Building", "Tile Placement"),
            plays_count=9800,
            **extra,
        )

    def _make_record_with_summary(self, bgg_id: int = 600010) -> BGGDetailRecord:
        base = self._make_base_record(bgg_id)
        return BGGDetailRecord(
            bgg_id=base.bgg_id,
            name=base.name,
            year=base.year,
            min_players=base.min_players,
            max_players=base.max_players,
            playing_time=base.playing_time,
            min_playing_time=base.min_playing_time,
            max_playing_time=base.max_playing_time,
            item_type=base.item_type,
            bgg_url=base.bgg_url,
            designers=base.designers,
            publishers=base.publishers,
            mechanics=base.mechanics,
            categories=base.categories,
            rating_bayes_average=base.rating_bayes_average,
            rating_average=base.rating_average,
            rating_median=base.rating_median,
            rating_stddev=base.rating_stddev,
            rating_num_weights=base.rating_num_weights,
            bgg_rank=base.bgg_rank,
            boardgame_rank=base.boardgame_rank,
            users_rated=base.users_rated,
            users_owned=base.users_owned,
            thumbnail=base.thumbnail,
            image=base.image,
            description=base.description,
            expansions=base.expansions,
            expands=base.expands,
            alternative_names=base.alternative_names,
            designers_list=base.designers_list,
            publishers_list=base.publishers_list,
            mechanics_list=base.mechanics_list,
            categories_list=base.categories_list,
            families=base.families,
            plays_count=base.plays_count,
            numplayers_summary={
                "bestwith": "Best with 6–8 players",
                "recommendedwith": "Recommended with 4–11 players",
            },
        )

    def test_numplayers_summary_is_persisted(self):
        """A record with numplayers_summary stores it on metadata."""

        record = self._make_record_with_summary(bgg_id=600011)
        result = upsert_detail(record)
        meta = BGGMetadata.objects.get(pk=result.metadata.pk)

        self.assertEqual(
            meta.numplayers_summary,
            {
                "bestwith": "Best with 6–8 players",
                "recommendedwith": "Recommended with 4–11 players",
            },
        )

    def test_numplayers_summary_none_preserves_existing(self):
        """Partial fetch with numplayers_summary=None keeps existing value."""

        record_full = self._make_record_with_summary(bgg_id=600012)
        upsert_detail(record_full)

        # Verify stored.
        meta = BGGMetadata.objects.get(bgg_id=600012)
        self.assertIsNotNone(meta.numplayers_summary)

        # Now partial fetch omits numplayers_summary (None).
        partial_record = BGGDetailRecord(
            bgg_id=600012,
            name="Updated Name",
            year=None,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
            item_type=None,
            bgg_url=None,
            designers=None,
            publishers=None,
            mechanics=None,
            categories=None,
            rating_bayes_average=None,
            rating_average=None,
            rating_median=None,
            rating_stddev=None,
            rating_num_weights=None,
            bgg_rank=None,
            boardgame_rank=None,
            users_rated=None,
            users_owned=None,
            thumbnail=None,
            image=None,
            description=None,
            expansions=(),
            expands=(),
            alternative_names=(),
            designers_list=(),
            publishers_list=(),
            mechanics_list=(),
            categories_list=(),
            families=(),
            plays_count=None,
            numplayers_summary=None,  # explicitly omitted
        )
        upsert_detail(partial_record)

        # Existing numplayers_summary must be preserved.
        refreshed = BGGMetadata.objects.get(bgg_id=600012)
        self.assertIsNotNone(refreshed.numplayers_summary)
        self.assertEqual(
            refreshed.numplayers_summary,
            {
                "bestwith": "Best with 6–8 players",
                "recommendedwith": "Recommended with 4–11 players",
            },
        )


class SuggestedPlayersUpsertTest(TestCase):
    """Verify suggested_players persistence through upsert."""

    def _make_full_record(self, bgg_id: int = 600000) -> BGGDetailRecord:
        record = self._make_record(bgg_id)
        return BGGDetailRecord(
            bgg_id=record.bgg_id,
            name=record.name,
            year=record.year,
            min_players=record.min_players,
            max_players=record.max_players,
            playing_time=record.playing_time,
            min_playing_time=record.min_playing_time,
            max_playing_time=record.max_playing_time,
            item_type=record.item_type,
            bgg_url=record.bgg_url,
            designers=record.designers,
            publishers=record.publishers,
            mechanics=record.mechanics,
            categories=record.categories,
            rating_bayes_average=record.rating_bayes_average,
            rating_average=record.rating_average,
            rating_median=record.rating_median,
            rating_stddev=record.rating_stddev,
            rating_num_weights=record.rating_num_weights,
            bgg_rank=record.bgg_rank,
            boardgame_rank=record.boardgame_rank,
            users_rated=record.users_rated,
            users_owned=record.users_owned,
            thumbnail=record.thumbnail,
            image=record.image,
            description=record.description,
            expansions=record.expansions,
            expands=record.expands,
            alternative_names=record.alternative_names,
            designers_list=record.designers_list,
            publishers_list=record.publishers_list,
            mechanics_list=record.mechanics_list,
            categories_list=record.categories_list,
            families=record.families,
            plays_count=record.plays_count,
            suggested_players=(
                {"numplayers": "1", "best": 10, "recommended": 5},
                {"numplayers": "2", "best": 3, "recommended": 20},
                {"numplayers": "4", "notrecommended": 1},
            ),
        )

    def _make_record(
        self,
        bgg_id: int = 600000,
        name: str | None = "Terra Mystica Extended",
        year: int = 2012,
        expansions: tuple[int, ...] = (),
        expands: tuple[int, ...] = (),
        **extra,
    ) -> BGGDetailRecord:
        return BGGDetailRecord(
            bgg_id=bgg_id,
            name=name,
            year=year,
            min_players=2,
            max_players=4,
            playing_time=120,
            min_playing_time=90,
            max_playing_time=150,
            item_type="boardgame",
            bgg_url=f"https://boardgamegeek.com/boardgame/{bgg_id}",
            designers="Stefan Feld",
            publishers="Clemson University",
            mechanics="Area Influence, Set Collection",
            categories="Farming, Strategy",
            rating_bayes_average=4.12,
            rating_average=4.35,
            rating_median=4.5,
            rating_stddev=0.8,
            rating_num_weights=2.8,
            bgg_rank=4,
            boardgame_rank=4,
            users_rated=45000,
            users_owned=12000,
            thumbnail="https://thumb.example.com/tm.jpg",
            image="https://img.example.com/tm.jpg",
            description="A fantasy civilization game.",
            expansions=expansions,
            expands=expands,
            alternative_names=("Terra Mystica HD", "Terra GM"),
            families=("Engine Building", "Tile Placement"),
            plays_count=9800,
            suggested_players=(
                {"numplayers": "1", "best": 10, "recommended": 5},
                {"numplayers": "2", "best": 3, "recommended": 20},
                {"numplayers": "4", "notrecommended": 1},
            ),
            **extra,
        )

    def test_suggested_players_is_persisted(self):
        """A record with suggested_players stores it on metadata."""

        record = self._make_full_record(bgg_id=600001)
        result = upsert_detail(record)
        meta = BGGMetadata.objects.get(pk=result.metadata.pk)

        self.assertEqual(
            meta.suggested_players,
            [
                {"numplayers": "1", "best": 10, "recommended": 5},
                {"numplayers": "2", "best": 3, "recommended": 20},
                {"numplayers": "4", "notrecommended": 1},
            ],
        )

    def test_suggested_players_none_preserves_existing(self):
        """Partial fetch with suggested_players=None keeps existing value."""

        record_full = self._make_full_record(bgg_id=600002)
        upsert_detail(record_full)

        # Verify stored.
        meta = BGGMetadata.objects.get(bgg_id=600002)
        self.assertIsNotNone(meta.suggested_players)

        # Now partial fetch omits suggested_players (None).
        partial_record = BGGDetailRecord(
            bgg_id=600002,
            name="Updated Name",
            year=None,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
            item_type=None,
            bgg_url=None,
            designers=None,
            publishers=None,
            mechanics=None,
            categories=None,
            rating_bayes_average=None,
            rating_average=None,
            rating_median=None,
            rating_stddev=None,
            rating_num_weights=None,
            bgg_rank=None,
            boardgame_rank=None,
            users_rated=None,
            users_owned=None,
            thumbnail=None,
            image=None,
            description=None,
            expansions=(),
            expands=(),
            alternative_names=(),
            designers_list=(),
            publishers_list=(),
            mechanics_list=(),
            categories_list=(),
            families=(),
            plays_count=None,
            suggested_players=None,  # explicitly omitted
        )
        upsert_detail(partial_record)

        # Existing suggested_players must be preserved.
        refreshed = BGGMetadata.objects.get(bgg_id=600002)
        self.assertIsNotNone(refreshed.suggested_players)
        self.assertEqual(
            refreshed.suggested_players,
            [
                {"numplayers": "1", "best": 10, "recommended": 5},
                {"numplayers": "2", "best": 3, "recommended": 20},
                {"numplayers": "4", "notrecommended": 1},
            ],
        )
