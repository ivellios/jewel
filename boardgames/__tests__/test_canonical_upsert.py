"""Focused service tests for canonical metadata upsert."""

from django.test import TestCase

from boardgames.bgg import BGGDetailRecord
from boardgames.models import BGGExpansion, BGGMetadata, BoardGame
from boardgames.services import upsert_detail
from boardgames.services.canonical_upsert import UpsertResult

from ..__tests__.factories import (
    BGGExpansionFactory,
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
            alternative_names=(),
            designers_list=(),
            publishers_list=(),
            mechanics_list=(),
            categories_list=(),
            families=(),
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
        )
        upsert_detail(empty_record)

        meta = BGGMetadata.objects.get(bgg_id=500008)
        self.assertEqual(meta.name, "Terra Mystica Extended")
        self.assertEqual(meta.yearpublished, 2012)


class UpsertExpansionLinksTest(TestCase):
    """Verify expansion/expands link behaviour."""

    def _make_record(
        self,
        bgg_id: int = 600000,
        expansions: tuple[int, ...] = (),
        expands: tuple[int, ...] = (),
    ) -> BGGDetailRecord:
        return BGGDetailRecord(
            bgg_id=bgg_id,
            name="Test Game",
            year=2012,
            min_players=None,
            max_players=None,
            playing_time=None,
            min_playing_time=None,
            max_playing_time=None,
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
            expansions=expansions,
            expands=expands,
            alternative_names=(),
            designers_list=(),
            publishers_list=(),
            mechanics_list=(),
            categories_list=(),
            families=(),
        )

    def test_creates_expansion_links_for_new_base(self):
        """A new base game gets links to pre-existing expansions."""

        BGGMetadata.objects.create(bgg_id=600001, name="Expansion A")
        BGGMetadata.objects.create(bgg_id=600002, name="Expansion B")

        base_record = self._make_record(
            bgg_id=600000,
            expansions=(600001, 600002),
        )
        result = upsert_detail(base_record)

        self.assertEqual(len(result.expansion_links), 2)
        link_ids = {(l.expansion.bgg_id, l.parent.bgg_id) for l in result.expansion_links}
        self.assertEqual(
            link_ids,
            {(600001, 600000), (600002, 600000)},
        )

    def test_creates_expands_links_for_new_base(self):
        """A new base game gets links to pre-existing expanded-into games."""

        BGGMetadata.objects.create(bgg_id=600001, name="Base Game A")
        BGGMetadata.objects.create(bgg_id=600002, name="Base Game B")

        base_record = self._make_record(
            bgg_id=600000,
            expands=(600001, 600002),
        )
        result = upsert_detail(base_record)

        self.assertEqual(len(result.expansion_links), 2)
        link_ids = {(l.expansion.bgg_id, l.parent.bgg_id) for l in result.expansion_links}
        self.assertEqual(
            link_ids,
            {(600000, 600001), (600000, 600002)},
        )

    def test_no_links_when_expansions_do_not_exist(self):
        """If expansion rows do not exist, no links are created."""

        base_record = self._make_record(
            bgg_id=600000,
            expansions=(999999, 888888),
        )
        result = upsert_detail(base_record)

        self.assertEqual(len(result.expansion_links), 0)
        self.assertEqual(BGGExpansion.objects.count(), 0)

    def test_duplicate_links_are_safe(self):
        """Calling upsert_detail twice creates exactly one link per pair."""

        BGGMetadata.objects.create(bgg_id=600001, name="Expansion A")
        BGGMetadata.objects.create(bgg_id=600002, name="Expansion B")

        base_record = self._make_record(
            bgg_id=600000,
            expansions=(600001, 600002),
        )

        upsert_detail(base_record)
        result2 = upsert_detail(base_record)

        # After first call: 2 links (both created).
        self.assertEqual(BGGExpansion.objects.count(), 2)
        # Second call: 0 new links (both already existed).
        self.assertEqual(len(result2.expansion_links), 0)

    def test_self_link_is_skipped(self):
        """A game expanding into itself is silently skipped."""

        # Create expansion metadata so the non-self link can be created.
        BGGMetadata.objects.create(bgg_id=600001, name="Expansion A")

        base_record = self._make_record(
            bgg_id=600000,
            expansions=(600000, 600001),  # 600000 = self → skipped
        )
        result = upsert_detail(base_record)

        # Only the non-self link (600001 -> 600000) is created.
        self.assertEqual(len(result.expansion_links), 1)
        self.assertEqual(
            result.expansion_links[0].expansion.bgg_id, 600001
        )
        self.assertEqual(
            result.expansion_links[0].parent.bgg_id, 600000
        )

    def test_upsert_on_existing_metadata_creates_no_links(self):
        """Updating existing metadata (new=False) creates no links."""

        BGGMetadata.objects.create(bgg_id=600000, name="Old")
        BGGMetadata.objects.create(bgg_id=600001, name="Expansion A")

        base_record = self._make_record(
            bgg_id=600000,
            expansions=(600001,),
        )
        result = upsert_detail(base_record)

        # The expansion metadata already existed, so no new links.
        self.assertEqual(len(result.expansion_links), 0)


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
