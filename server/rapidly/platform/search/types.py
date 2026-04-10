"""Pydantic schemas for cross-entity search requests and responses."""

from typing import Annotated, Literal

from pydantic import UUID4, Discriminator, TypeAdapter

from rapidly.core.types import Schema

type SearchResultType = Literal["share", "customer"]


class SearchResultProduct(Schema):
    type: Literal["share"] = "share"
    id: UUID4
    name: str
    description: str | None = None


class SearchResultCustomer(Schema):
    type: Literal["customer"] = "customer"
    id: UUID4
    name: str | None
    email: str


SearchResult = Annotated[
    SearchResultProduct | SearchResultCustomer,
    Discriminator("type"),
]

SearchResultTypeAdapter: TypeAdapter[SearchResult] = TypeAdapter(SearchResult)


class SearchResults(Schema):
    results: list[SearchResult]
