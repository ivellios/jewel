"""Raw BoardGameGeek transport boundary.

Only this module knows about ``boardgamegeek``.  Its methods deliberately
return the library's raw response objects for the adapter/repository layer to
normalise; Django services must use Jewel-owned records instead.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any
from xml.etree import ElementTree

from boardgamegeek import (
    BGGApiError,
    BGGApiTimeoutError,
    BGGError,
    BGGItemNotFoundError,
)
from boardgamegeek import BGGClient as BoardGameGeekClient
from boardgamegeek.api import Collection, add_collection_items_from_xml
from boardgamegeek.loaders.game import create_game_from_xml
from boardgamegeek.utils import request_and_parse_xml

from .errors import (
    BGGAdapterError,
    BGGCredentialMissingError,
    BGGNetworkError,
    BGGNotFoundError,
)

DEFAULT_BGG_API_URL = "https://boardgamegeek.com/xmlapi2"


class BGGClient:
    """Configure and call the third-party BGG client.

    Raw values returned here are an internal contract for the BGG adapter and
    repository only.  This class owns the vendor client, endpoint, credentials,
    timeout, and conversion to Jewel-owned exceptions.
    """

    def __init__(
        self,
        access_token: str,
        api_url: str = DEFAULT_BGG_API_URL,
        timeout: float = 30,
    ) -> None:
        if not access_token:
            raise BGGCredentialMissingError(
                "BGG access_token is required; set BGG_ACCESS_TOKEN before "
                "creating BGGClient."
            )

        self._api_url = api_url.rstrip("/")
        self._timeout = timeout
        self._client = BoardGameGeekClient(
            access_token=access_token,
            timeout=timeout,
        )
        self._configure_endpoint()

    def game(self, game_id: int) -> Any:
        """Return the raw game response."""
        return self._call(game_id, self._client.game, game_id=game_id)

    def collection(
        self,
        user_name: str,
        ids: Iterable[int] | None = None,
        **filters: Any,
    ) -> Any:
        """Return the raw collection item responses.

        The vendor collection wrapper deduplicates by game ID. Parse each XML
        item separately so editions retain their distinct BGG collection IDs.
        """
        # The vendor Collection object deduplicates by game ID, but BGG allows
        # multiple collection entries (and editions) for the same game.
        subtype = str(filters.get("subtype", "boardgame"))
        params: dict[str, object] = {
            "username": user_name,
            "subtype": subtype,
            "stats": 1,
        }
        if ids is not None:
            params["id"] = ",".join(map(str, ids))
        filter_parameters = {
            "exclude_subtype": "excludesubtype",
            "version": "version",
            "own": "own",
            "rated": "rated",
            "played": "played",
            "commented": "comment",
            "trade": "trade",
            "want": "want",
            "wishlist": "wishlist",
            "wishlist_prio": "wishlishpriority",
            "preordered": "preordered",
            "want_to_play": "wanttoplay",
            "want_to_buy": "wanttobuy",
            "prev_owned": "prevowned",
            "has_parts": "hasparts",
            "want_parts": "wantparts",
            "min_rating": "minrating",
            "rating": "rating",
            "min_bgg_rating": "minbggrating",
            "bgg_rating": "bggrating",
            "min_plays": "minplays",
            "max_plays": "maxplays",
            "collection_id": "collid",
            "modified_since": "modifiedsince",
        }
        if filters.get("version") is None and filters.get("versions") is not None:
            filter_parameters["versions"] = "version"
        for key, parameter in filter_parameters.items():
            value = filters.get(key)
            if value is not None:
                params[parameter] = int(value) if isinstance(value, bool) else value
        try:
            root = request_and_parse_xml(
                self._client.requests_session,
                self._client._collection_api_url,
                params=params,
                timeout=self._timeout,
                retries=self._client._retries,
                retry_delay=self._client._retry_delay,
                headers=self._client._get_auth_headers(),
            )
            error = root.find(".//error")
            if error is not None:
                raise BGGItemNotFoundError(
                    error.findtext("message") or "BGG collection not found"
                )
            records = []
            for item in root.findall(f"item[@subtype='{subtype}']"):
                single_item = ElementTree.Element("items")
                single_item.append(item)
                collection = Collection({"owner": user_name})
                add_collection_items_from_xml(collection, single_item, subtype)
                if collection.items:
                    record = collection.items[0]
                    record._data["collection_id"] = item.attrib.get("collid")
                    records.append(record)
            return records
        except BGGError as exc:
            self._raise_mapped_error(exc, user_name)

    def plays(
        self,
        *,
        name: str | None = None,
        game_id: int | None = None,
        min_date: date | None = None,
        max_date: date | None = None,
        subtype: str = "boardgame",
    ) -> Any:
        """Return the raw plays response."""
        return self._call(
            game_id or name or "plays",
            self._client.plays,
            name=name,
            game_id=game_id,
            min_date=min_date,
            max_date=max_date,
            subtype=subtype,
        )

    def game_list(self, game_ids: Iterable[int]) -> Any:
        """Return raw responses including per-edition localized titles."""
        ids = list(game_ids)
        if not ids:
            return []
        try:
            root = request_and_parse_xml(
                self._client.requests_session,
                self._client._thing_api_url,
                params={"id": ",".join(map(str, ids)), "versions": 1, "stats": 1},
                timeout=self._timeout,
                retries=self._client._retries,
                retry_delay=self._client._retry_delay,
                headers=self._client._get_auth_headers(),
            )
            results = []
            for element in root.findall("item"):
                game_id = int(element.attrib["id"])
                game = create_game_from_xml(element, game_id=game_id)
                localized_versions = []
                for version in element.findall("versions/item"):
                    language_link = version.find("link[@type='language']")
                    localized_name = version.find("canonicalname")
                    localized_versions.append(
                        {
                            "id": int(version.attrib["id"]),
                            "language": language_link.attrib.get("value")
                            if language_link is not None
                            else None,
                            "canonical_name": localized_name.attrib.get("value")
                            if localized_name is not None
                            else None,
                        }
                    )
                # Attach per-game poll-summary as a plain mapping that the
                # adapter's _poll_summary recognises (Mapping · Mapping · list).
                # In real BGG XML, poll-summary is a direct child of item,
                # not wrapped inside <suggested_numplayers>.
                poll = element.find("poll-summary[@name='suggested_numplayers']")
                if poll is not None:
                    game._data["suggested_numplayers"] = {
                        "poll-summary": {
                            "result": [dict(r.attrib) for r in poll.findall("result")],
                        },
                    }
                results.append({**game._data, "localized_versions": localized_versions})
            if {item["id"] for item in results} != set(ids):
                raise BGGApiError("BGG detail batch returned an unexpected set of IDs")
            return results
        except BGGError as exc:
            self._raise_mapped_error(exc, ids)

    def search(
        self,
        query: str,
        search_type: list[str] | None = None,
        exact: bool = False,
    ) -> Any:
        """Return raw search responses."""
        return self._call(query, self._client.search, query, search_type, exact)

    def _configure_endpoint(self) -> None:
        """Apply the configured base URL to every vendor endpoint.

        ``boardgamegeek`` currently hard-codes its endpoint in its constructor,
        so its endpoint attributes must be updated after construction.  Keeping
        that private-library detail here ensures a configured URL is never
        silently ignored elsewhere in the application.
        """
        for endpoint in (
            "search",
            "thing",
            "guild",
            "user",
            "plays",
            "hot",
            "collection",
        ):
            setattr(self._client, f"_{endpoint}_api_url", f"{self._api_url}/{endpoint}")

    def _call(self, context: Any, method: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return method(*args, **kwargs)
        except BGGError as exc:
            self._raise_mapped_error(exc, context)

    @staticmethod
    def _raise_mapped_error(exc: BGGError, context: Any) -> None:
        if isinstance(exc, BGGItemNotFoundError):
            raise BGGNotFoundError(f"BGG resource not found: {context}") from exc
        if isinstance(exc, BGGApiError | BGGApiTimeoutError):
            raise BGGNetworkError(f"Network / API error for {context}: {exc}") from exc
        raise BGGAdapterError(f"Unexpected BGG error for {context}: {exc}") from exc
