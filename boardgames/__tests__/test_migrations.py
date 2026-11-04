"""Data-preservation coverage for board game schema migrations."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ImportedCopyIdentityMigrationTest(TransactionTestCase):
    """Legacy imported copies are normalized before identity constraints apply."""

    migrate_from = (
        "boardgames",
        "0004_bggmetadata_alternative_names_bggmetadata_bgg_rank_and_more",
    )
    migrate_to = (
        "boardgames",
        "0005_boardgame_boardgames_imported_copy_requires_metadata_and_more",
    )

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])
        self.old_apps = self.executor.loader.project_state([self.migrate_from]).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate([self.migrate_to])
        super().tearDown()

    def test_anonymous_and_duplicate_imports_become_local_without_deletion(self):
        metadata_model = self.old_apps.get_model("boardgames", "BGGMetadata")
        board_game_model = self.old_apps.get_model("boardgames", "BoardGame")
        metadata = metadata_model.objects.create(bgg_id=991001, name="Source game")

        anonymous = board_game_model.objects.create(name="Anonymous", imported=True)
        imported_a = board_game_model.objects.create(
            name="Imported A", imported=True, metadata=metadata
        )
        imported_b = board_game_model.objects.create(
            name="Imported B", imported=True, metadata=metadata
        )

        new_state = MigrationExecutor(connection).migrate([self.migrate_to])
        board_game_model = new_state.apps.get_model("boardgames", "BoardGame")

        self.assertFalse(board_game_model.objects.get(pk=anonymous.pk).imported)
        self.assertEqual(
            board_game_model.objects.filter(metadata_id=metadata.pk).count(), 2
        )
        self.assertEqual(
            board_game_model.objects.filter(
                metadata_id=metadata.pk, imported=True
            ).count(),
            1,
        )
        self.assertEqual(
            board_game_model.objects.filter(
                pk__in=[imported_a.pk, imported_b.pk], imported=False
            ).count(),
            1,
        )
