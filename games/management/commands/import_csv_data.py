from django.core.management import BaseCommand

from csv_importer.importers import CSVGamesImporter
from games.repositories import DjangoGameRepository


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("file_path", help="Path to the CSV data file")

    def handle(self, *args, **options):
        file_path = options.get("file_path")

        importer = CSVGamesImporter(
            file_path,
            DjangoGameRepository(),
        )

        importer.load_data()
        importer.process()
