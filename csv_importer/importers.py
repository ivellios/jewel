from collections.abc import Callable
from typing import Any

import numpy
import pandas
from tqdm import tqdm

from abstract.repositories import GameRepository

from .adapters import CSVGameAdapter


class CSVGamesImporter:
    data: list[dict[Any, Any]] | None = None

    def __init__(
        self,
        file_path: str,
        repository: GameRepository,
        adapter_class: Callable[[dict[Any, Any]], CSVGameAdapter] = CSVGameAdapter,
    ):
        self.file_path = file_path
        self.repository = repository
        self.adapter_class = adapter_class

    def load_data(self):
        self.data = (
            pandas.read_csv(
                self.file_path,
                na_values=[None],  # type: ignore[list-item]  # Pandas accepts None as an NA sentinel.
            )
            .astype(object)
            .replace(numpy.nan, None)
            .replace("x", True)
            .replace("X", True)
            .to_dict("records")
        )

    def process(self):
        if self.data is None:
            self.load_data()
        data = self.data
        if data is None:
            return
        for game_data in tqdm(data, total=len(data)):
            data_adapter = self.adapter_class(game_data)
            if not data_adapter.name:
                continue
            model, created = self.repository.create(data_adapter)
            if not created:
                tqdm.write(f"Duplicate {model.name}")
