import numpy
import pandas
from tqdm import tqdm

from games.repositories import DjangoGameRepository
from .adapters import CSVGameAdapter


class CSVGamesImporter:
    def __init__(self):
        self.file = "data.csv"
        self.data = (
            pandas.read_csv(self.file, na_values=[None])
            .astype(object)
            .replace(numpy.nan, None)
            .replace("x", True)
            .replace("X", True)
            .to_dict("records")
        )
        self.repository = DjangoGameRepository
        self.adapter_class = CSVGameAdapter

    def process(self):
        for game_data in tqdm(self.data, total=len(self.data)):
            data_adapter = self.adapter_class(game_data)
            if not data_adapter.title:
                continue
            model, created = self.repository.create(data_adapter)
            if not created:
                tqdm.write(f"Duplicate {model.title}")
