import os
import tempfile
from unittest.mock import Mock, patch

from abstract.repositories import GameRepository
from csv_importer.adapters import CSVGameAdapter
from csv_importer.importers import CSVGamesImporter


class TestCSVGamesImporter:
    def test_init_sets_attributes(self):
        """Test that __init__ correctly sets instance attributes"""
        file_path = "/test/path.csv"
        mock_repository = Mock(spec=GameRepository)

        importer = CSVGamesImporter(file_path, mock_repository)

        assert importer.file_path == file_path
        assert importer.repository == mock_repository
        assert importer.adapter_class == CSVGameAdapter
        assert importer.data is None

    def test_init_with_custom_adapter(self):
        """Test __init__ with custom adapter class"""
        file_path = "/test/path.csv"
        mock_repository = Mock(spec=GameRepository)
        custom_adapter = Mock()

        importer = CSVGamesImporter(file_path, mock_repository, custom_adapter)

        assert importer.adapter_class == custom_adapter

    @patch("csv_importer.importers.pandas.read_csv")
    def test_load_data_processes_csv_correctly(self, mock_read_csv):
        """Test that load_data processes CSV with correct transformations"""
        # Setup mock data
        mock_df = Mock()
        mock_df.astype.return_value = mock_df
        mock_df.replace.return_value = mock_df
        mock_df.to_dict.return_value = [
            {"name": "Test Game", "platform_1": "PC", "played": True}
        ]
        mock_read_csv.return_value = mock_df

        file_path = "/test/path.csv"
        mock_repository = Mock(spec=GameRepository)
        importer = CSVGamesImporter(file_path, mock_repository)

        importer.load_data()

        # Verify pandas.read_csv was called correctly
        mock_read_csv.assert_called_once_with("/test/path.csv", na_values=[None])

        # Verify data is set
        assert importer.data == [
            {"name": "Test Game", "platform_1": "PC", "played": True}
        ]

    @patch("csv_importer.importers.pandas.read_csv")
    def test_load_data_handles_x_replacements(self, mock_read_csv):
        """Test that load_data correctly replaces x/X with True"""
        mock_df = Mock()
        mock_df.astype.return_value = mock_df
        mock_df.replace.return_value = mock_df
        mock_df.to_dict.return_value = []
        mock_read_csv.return_value = mock_df

        file_path = "/test/path.csv"
        mock_repository = Mock(spec=GameRepository)
        importer = CSVGamesImporter(file_path, mock_repository)

        importer.load_data()

        # Verify replacement calls
        replace_calls = mock_df.replace.call_args_list
        # Should replace: numpy.nan -> None, "x" -> True, "X" -> True
        assert len(replace_calls) == 3
        assert replace_calls[1] == (("x", True),)
        assert replace_calls[2] == (("X", True),)

    @patch("csv_importer.importers.tqdm")
    def test_process_calls_load_data_if_no_data(self, mock_tqdm):
        """Test that process calls load_data if data is None"""
        mock_repository = Mock(spec=GameRepository)
        importer = CSVGamesImporter("/test/path.csv", mock_repository)

        # Mock load_data to avoid actual file I/O
        importer.load_data = Mock()
        importer.load_data.side_effect = lambda: setattr(importer, "data", [])

        importer.process()

        importer.load_data.assert_called_once()

    @patch("csv_importer.importers.tqdm")
    def test_process_skips_load_data_if_data_exists(self, mock_tqdm):
        """Test that process doesn't call load_data if data already exists"""
        mock_repository = Mock(spec=GameRepository)
        importer = CSVGamesImporter("/test/path.csv", mock_repository)

        # Set existing data
        importer.data = []
        importer.load_data = Mock()

        importer.process()

        importer.load_data.assert_not_called()

    @patch("csv_importer.importers.tqdm")
    def test_process_skips_games_without_name(self, mock_tqdm):
        """Test that process skips games with no name"""
        mock_tqdm.return_value = []
        mock_repository = Mock(spec=GameRepository)
        mock_adapter_class = Mock()

        # Mock adapter that returns empty name
        mock_adapter = Mock()
        mock_adapter.name = None
        mock_adapter_class.return_value = mock_adapter

        importer = CSVGamesImporter(
            "/test/path.csv", mock_repository, mock_adapter_class
        )
        importer.data = [{"name": ""}]  # Empty name data

        importer.process()

        # Verify repository.create was not called
        mock_repository.create.assert_not_called()

    @patch("csv_importer.importers.tqdm")
    def test_process_creates_games_with_valid_data(self, mock_tqdm):
        """Test that process creates games for valid data"""
        mock_tqdm.return_value = [{"name": "Test Game"}]
        mock_tqdm.write = Mock()

        mock_repository = Mock(spec=GameRepository)
        mock_adapter_class = Mock()

        # Mock adapter with valid name
        mock_adapter = Mock()
        mock_adapter.name = "Test Game"
        mock_adapter_class.return_value = mock_adapter

        # Mock repository create response (new game)
        mock_game = Mock()
        mock_game.name = "Test Game"
        mock_repository.create.return_value = (mock_game, True)

        importer = CSVGamesImporter(
            "/test/path.csv", mock_repository, mock_adapter_class
        )
        importer.data = [{"name": "Test Game"}]

        importer.process()

        # Verify adapter was created with correct data
        mock_adapter_class.assert_called_once_with({"name": "Test Game"})

        # Verify repository.create was called with adapter
        mock_repository.create.assert_called_once_with(mock_adapter)

        # Verify no duplicate message (created=True)
        mock_tqdm.write.assert_not_called()

    @patch("csv_importer.importers.tqdm")
    def test_process_handles_duplicates(self, mock_tqdm):
        """Test that process handles duplicate games correctly"""
        mock_tqdm.return_value = [{"name": "Duplicate Game"}]
        mock_tqdm.write = Mock()

        mock_repository = Mock(spec=GameRepository)
        mock_adapter_class = Mock()

        # Mock adapter
        mock_adapter = Mock()
        mock_adapter.name = "Duplicate Game"
        mock_adapter_class.return_value = mock_adapter

        # Mock repository create response (duplicate game)
        mock_game = Mock()
        mock_game.name = "Duplicate Game"
        mock_repository.create.return_value = (mock_game, False)  # created=False

        importer = CSVGamesImporter(
            "/test/path.csv", mock_repository, mock_adapter_class
        )
        importer.data = [{"name": "Duplicate Game"}]

        importer.process()

        # Verify duplicate message was written
        mock_tqdm.write.assert_called_once_with("Duplicate Duplicate Game")

    @patch("csv_importer.importers.tqdm")
    def test_process_handles_multiple_games(self, mock_tqdm):
        """Test that process handles multiple games correctly"""
        game_data = [
            {"name": "Game 1"},
            {"name": ""},  # Should be skipped
            {"name": "Game 2"},
        ]
        mock_tqdm.return_value = game_data
        mock_tqdm.write = Mock()

        mock_repository = Mock(spec=GameRepository)
        mock_adapter_class = Mock()

        # Mock adapters - first and third valid, second invalid
        adapters = []
        for _, data in enumerate(game_data):
            adapter = Mock()
            adapter.name = data["name"] if data["name"] else None
            adapters.append(adapter)

        mock_adapter_class.side_effect = adapters

        # Mock repository responses
        mock_games = []
        for i in range(2):  # Only 2 valid games
            game = Mock()
            game.name = f"Game {i + 1}"
            mock_games.append((game, True))

        mock_repository.create.side_effect = mock_games

        importer = CSVGamesImporter(
            "/test/path.csv", mock_repository, mock_adapter_class
        )
        importer.data = game_data

        importer.process()

        # Verify create was called twice (skipped empty name)
        assert mock_repository.create.call_count == 2
        mock_repository.create.assert_any_call(adapters[0])  # Game 1
        mock_repository.create.assert_any_call(adapters[2])  # Game 2 (skipped index 1)


class TestCSVGamesImporterIntegration:
    """Integration tests with real CSV files"""

    def test_load_data_with_real_csv(self):
        """Test load_data with a real CSV file"""
        csv_content = """name,platform_1,played,controller_support
Test Game,PC,x,X
Another Game,PlayStation,X,x"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            mock_repository = Mock(spec=GameRepository)
            importer = CSVGamesImporter(temp_path, mock_repository)

            importer.load_data()

            assert len(importer.data) == 2
            assert importer.data[0]["name"] == "Test Game"
            assert importer.data[0]["played"] is True  # x -> True
            assert importer.data[0]["controller_support"] is True  # X -> True
            assert importer.data[1]["name"] == "Another Game"
            assert importer.data[1]["played"] is True  # X -> True
            assert importer.data[1]["controller_support"] is True  # x -> True

        finally:
            os.unlink(temp_path)

    @patch("csv_importer.importers.tqdm")
    def test_full_process_integration(self, mock_tqdm):
        """Test full process integration with CSV file and repository"""
        csv_content = """name,platform_1,vendor
Game 1,PC,Steam
Game 2,PlayStation,Sony"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            # Mock tqdm to return the data for processing
            mock_tqdm.side_effect = lambda data, total: data
            mock_tqdm.write = Mock()

            mock_repository = Mock(spec=GameRepository)
            mock_repository.create.side_effect = [
                (Mock(name="Game 1"), True),  # First game created
                (Mock(name="Game 2"), False),  # Second game is duplicate
            ]

            importer = CSVGamesImporter(temp_path, mock_repository)
            importer.process()

            # Verify both games were processed
            assert mock_repository.create.call_count == 2

            # Verify duplicate message for second game
            mock_tqdm.write.assert_called_once()
            call_args = mock_tqdm.write.call_args[0][0]
            assert "Duplicate" in call_args

        finally:
            os.unlink(temp_path)
