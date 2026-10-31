from django.test import TestCase

from collection_core.models import CollectionItem
from games.models import VideoGame


class CollectionItemTestCase(TestCase):
    def test_collection_item_is_abstract_with_shared_fields(self):
        self.assertTrue(CollectionItem._meta.abstract)
        self.assertEqual(
            {field.name for field in CollectionItem._meta.fields},
            {
                "name",
                "played",
                "review",
                "notes",
                "play_priority",
                "min_players",
                "max_players",
            },
        )

    def test_game_inherits_collection_item_fields(self):
        self.assertTrue(issubclass(VideoGame, CollectionItem))
        game = VideoGame()
        self.assertEqual(game.min_players, 1)
        self.assertEqual(game.max_players, 1)

    def test_game_retains_video_game_specific_fields(self):
        field_names = {field.name for field in VideoGame._meta.fields}
        many_to_many_names = {field.name for field in VideoGame._meta.many_to_many}
        self.assertTrue({"id", "controller_support", "party_fit"}.issubset(field_names))
        self.assertEqual(many_to_many_names, {"platforms", "genres"})
