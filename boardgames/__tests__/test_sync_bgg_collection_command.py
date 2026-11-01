"""Focused management-command tests for ``sync_bgg_collection``.

Tests:

* Missing required settings → ``stderr`` message + ``SystemExit(2)``.
* Full success → ``SystemExit(0)``, diagnostics printed to stdout.
* Partial failure → ``SystemExit(1)``, errors printed to stderr.
* Failed (collection fetch itself) → ``SystemExit(2)``, error details.
* Exit codes match ``BGGSyncRun.status`` mapping (full→0, partial→1, failed→2).
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from boardgames.bgg import BGGCollectionRecord
from boardgames.models import BGGSyncRun

# -----------------------------------------------------------------------
# Helpers / fixture builders (mirroring orchestration test helpers)
# -----------------------------------------------------------------------


def _make_collection_record(
    bgg_id: int = 900000,
    **extra,
) -> BGGCollectionRecord:
    """Convenience factory for BGGCollectionRecord fixtures."""

    return BGGCollectionRecord(
        bgg_id=bgg_id,
        name=None,
        rating=extra.get("rating"),
        numplays=extra.get("numplays", 0),
        owned=extra.get("owned", False),
        prev_owned=False,
        wishlist=False,
        wishlist_priority=None,
        want=False,
        want_to_play=False,
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


def _make_adapter(
    collection: tuple[BGGCollectionRecord, ...] = (),
    detail_records: tuple[dict, ...] | None = None,
    fail_collection: bool = False,
    fail_detail_ids: set[int] | None = None,
) -> MagicMock:
    """Build a mock BGGAdapter with predictable behaviour."""

    from boardgames.bgg.errors import BGGNetworkError, BGGNotFoundError

    mock = MagicMock()
    mock.get_collection.return_value = collection
    mock.get_collection.side_effect = None

    if fail_collection:
        mock.get_collection.side_effect = BGGNetworkError("connection refused")

    if detail_records is None:
        detail_records = ()

    def _get_detail_side_effect(bgg_id: int):
        from boardgames.bgg import BGGDetailRecord

        if fail_detail_ids and bgg_id in fail_detail_ids:
            raise BGGNotFoundError(f"Not found: {bgg_id}")
        for rec in detail_records:
            if rec.get("bgg_id") == bgg_id:
                return BGGDetailRecord(
                    bgg_id=rec["bgg_id"],
                    name=rec.get("name"),
                    year=rec.get("year"),
                    min_players=rec.get("min_players"),
                    max_players=rec.get("max_players"),
                    playing_time=rec.get("playing_time"),
                    min_playing_time=rec.get("min_playing_time"),
                    max_playing_time=rec.get("max_playing_time"),
                    designers=rec.get("designers"),
                    publishers=rec.get("publishers"),
                    mechanics=rec.get("mechanics"),
                    categories=rec.get("categories"),
                    rating_bayes_average=rec.get("rating_bayes_average"),
                    rating_average=rec.get("rating_average"),
                    rating_median=rec.get("rating_median"),
                    rating_stddev=rec.get("rating_stddev"),
                    rating_num_weights=rec.get("rating_num_weights"),
                    bgg_rank=rec.get("bgg_rank"),
                    boardgame_rank=rec.get("boardgame_rank"),
                    users_rated=rec.get("users_rated"),
                    users_owned=rec.get("users_owned"),
                    thumbnail=rec.get("thumbnail"),
                    image=rec.get("image"),
                    description=rec.get("description"),
                    expansions=rec.get("expansions", ()),
                    expands=rec.get("expands", ()),
                    alternative_names=rec.get("alternative_names", ()),
                    designers_list=rec.get("designers_list", ()),
                    publishers_list=rec.get("publishers_list", ()),
                    mechanics_list=rec.get("mechanics_list", ()),
                    categories_list=rec.get("categories_list", ()),
                    families=rec.get("families"),
                )
        return BGGDetailRecord(
            bgg_id=bgg_id,
            name=f"Game {bgg_id}",
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
            expansions=(),
            expands=(),
            alternative_names=(),
            designers_list=(),
            publishers_list=(),
            mechanics_list=(),
            categories_list=(),
            families=(),
        )

    mock.get_detail.side_effect = _get_detail_side_effect
    return mock


# -----------------------------------------------------------------------
# Tests: missing settings
# -----------------------------------------------------------------------


class MissingSettingsTest(TestCase):
    """Verify missing BGG settings produce clear errors."""

    def test_missing_access_token_raises_system_exit(self):
        """No BGG_ACCESS_TOKEN → SystemExit(2) with error message."""

        with (
            override_settings(BGG_ACCESS_TOKEN=None),
            patch("boardgames.management.commands.sync_bgg_collection.BGGAdapter"),
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit) as ctx:
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("Missing required settings", err.getvalue())
            self.assertIn("BGG_ACCESS_TOKEN", err.getvalue())

    def test_missing_user_name_raises_system_exit(self):
        """No BGG_USER_NAME → SystemExit(2) with error message."""

        with (
            override_settings(BGG_USER_NAME=None),
            patch("boardgames.management.commands.sync_bgg_collection.BGGAdapter"),
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit) as ctx:
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("Missing required settings", err.getvalue())
            self.assertIn("BGG_USER_NAME", err.getvalue())

    def test_both_settings_missing(self):
        """Both missing → error lists both."""

        with (
            override_settings(BGG_ACCESS_TOKEN=None, BGG_USER_NAME=None),
            patch("boardgames.management.commands.sync_bgg_collection.BGGAdapter"),
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit) as ctx:
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            self.assertEqual(ctx.exception.code, 2)
            err_text = err.getvalue()
            self.assertIn("BGG_ACCESS_TOKEN", err_text)
            self.assertIn("BGG_USER_NAME", err_text)


# -----------------------------------------------------------------------
# Tests: exit codes and output
# -----------------------------------------------------------------------


class ExitCodesTest(TestCase):
    """Verify exit codes match BGGSyncRun status."""

    def test_full_success_exits_zero(self):
        """Full reconciliation → SystemExit(0)."""

        collection = (
            _make_collection_record(bgg_id=901000),
            _make_collection_record(bgg_id=901001),
        )
        adapter = _make_adapter(collection)

        with patch(
            "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
            return_value=adapter,
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit) as ctx:
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            self.assertEqual(ctx.exception.code, 0)
            self.assertIn("Sync run:", out.getvalue())
            self.assertIn("full", out.getvalue())

    def test_partial_failure_exits_one(self):
        """Partial (some items fail) → SystemExit(1)."""

        collection = (
            _make_collection_record(bgg_id=901100),
            _make_collection_record(bgg_id=901101),
            _make_collection_record(bgg_id=901102),
        )
        adapter = _make_adapter(
            collection,
            fail_detail_ids={901101},
        )

        with patch(
            "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
            return_value=adapter,
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit) as ctx:
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("partial", out.getvalue())

    def test_failed_collection_exits_two(self):
        """Failed collection fetch → SystemExit(2)."""

        adapter = _make_adapter(fail_collection=True)

        with patch(
            "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
            return_value=adapter,
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit) as ctx:
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            self.assertEqual(ctx.exception.code, 2)
            self.assertIn("failed", out.getvalue())
            self.assertIn("Fetch successful: False", out.getvalue())


# -----------------------------------------------------------------------
# Tests: diagnostics output
# -----------------------------------------------------------------------


class DiagnosticsOutputTest(TestCase):
    """Verify output formatting (stdout / stderr)."""

    def test_full_success_prints_collection_and_counters(self):
        """Full success prints collection count, fetched, created, updated."""

        collection = (
            _make_collection_record(bgg_id=901200),
            _make_collection_record(bgg_id=901201),
        )
        adapter = _make_adapter(collection)

        with patch(
            "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
            return_value=adapter,
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit):
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            output = out.getvalue()
            self.assertIn("Sync run:", output)
            self.assertIn("Collection:", output)
            self.assertIn("items", output)
            self.assertIn("Fetched:", output)
            self.assertIn("Created:", output)
            self.assertIn("Updated:", output)
            self.assertIn("Removed:", output)
            self.assertIn("Restored:", output)
            self.assertIn("Fetch successful: True", output)

    def test_partial_failure_prints_errors_to_stderr(self):
        """Partial failure prints error details to stderr."""

        collection = (
            _make_collection_record(bgg_id=901300),
            _make_collection_record(bgg_id=901301),
        )
        adapter = _make_adapter(
            collection,
            fail_detail_ids={901301},
        )

        with patch(
            "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
            return_value=adapter,
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit):
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            self.assertIn("Errors:", err.getvalue())
            self.assertIn("901301", err.getvalue())

    def test_failed_collection_prints_error_to_stderr(self):
        """Failed (collection) prints error to stderr."""

        adapter = _make_adapter(fail_collection=True)

        with patch(
            "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
            return_value=adapter,
        ):
            out = StringIO()
            err = StringIO()
            with self.assertRaises(SystemExit):
                call_command(
                    "sync_bgg_collection",
                    stdout=out,
                    stderr=err,
                )
            self.assertIn("Fetch successful: False", out.getvalue())


# -----------------------------------------------------------------------
# Tests: persistent BGGSyncRun after command
# -----------------------------------------------------------------------


class SyncRunPersistenceAfterCommandTest(TestCase):
    """Verify BGGSyncRun is persisted after command execution."""

    def test_full_success_persists_sync_run(self):
        """Full success leaves a BGGSyncRun with status=full."""

        collection = (_make_collection_record(bgg_id=901400),)
        adapter = _make_adapter(collection)

        with (
            patch(
                "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
                return_value=adapter,
            ),
            self.assertRaises(SystemExit),
        ):
            call_command("sync_bgg_collection")

        sync_run = BGGSyncRun.objects.latest("created_at")
        self.assertEqual(sync_run.status, "full")
        self.assertTrue(sync_run.fetch_successful)
        self.assertEqual(sync_run.items_total, 1)

    def test_partial_failure_persists_sync_run(self):
        """Partial failure leaves a BGGSyncRun with status=partial."""

        collection = (
            _make_collection_record(bgg_id=901500),
            _make_collection_record(bgg_id=901501),
        )
        adapter = _make_adapter(
            collection,
            fail_detail_ids={901501},
        )

        with (
            patch(
                "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
                return_value=adapter,
            ),
            self.assertRaises(SystemExit),
        ):
            call_command("sync_bgg_collection")

        sync_run = BGGSyncRun.objects.latest("created_at")
        self.assertEqual(sync_run.status, "partial")
        self.assertTrue(sync_run.fetch_successful)
        self.assertEqual(sync_run.items_failed, 1)

    def test_failed_collection_persists_sync_run(self):
        """Failed collection leaves a BGGSyncRun with status=failed."""

        adapter = _make_adapter(fail_collection=True)

        with (
            patch(
                "boardgames.management.commands.sync_bgg_collection.BGGAdapter",
                return_value=adapter,
            ),
            self.assertRaises(SystemExit),
        ):
            call_command("sync_bgg_collection")

        sync_run = BGGSyncRun.objects.latest("created_at")
        self.assertEqual(sync_run.status, "failed")
        self.assertFalse(sync_run.fetch_successful)
