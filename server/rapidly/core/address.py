"""Address models, validation, and SQLAlchemy column type for postal addresses.

Provides ISO 3166-1 alpha-2 country enums (with embargo filtering),
US-state and Canadian-province subdivisions, a ``pydantic.BaseModel``
subclass with cross-field validation, and a custom SQLAlchemy
``TypeDecorator`` for transparent JSONB persistence.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any, NotRequired, Self, TypedDict, cast

import pycountry
from pydantic import BaseModel, BeforeValidator, Field, model_validator
from pydantic.json_schema import WithJsonSchema
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from rapidly.core.types import EmptyStrToNone

# ── Country sets ─────────────────────────────────────────────────────


class _CountryProtocol:
    """Structural type hint for pycountry country objects."""

    alpha_2: str


# Embargoed countries excluded from the supported set.
_EMBARGOED_COUNTRIES: frozenset[str] = frozenset({"CU", "IR", "KP", "SY", "RU"})

_ALL_COUNTRIES: set[str] = {
    cast(_CountryProtocol, country).alpha_2 for country in pycountry.countries
}
_SUPPORTED_COUNTRIES: set[str] = _ALL_COUNTRIES - _EMBARGOED_COUNTRIES

ALL_COUNTRIES = sorted(_ALL_COUNTRIES)
SUPPORTED_COUNTRIES = sorted(_SUPPORTED_COUNTRIES)


# ── Dynamic country enums ────────────────────────────────────────────

if TYPE_CHECKING:

    class CountryAlpha2(StrEnum):
        pass

    class CountryAlpha2Input(StrEnum):
        pass
else:
    CountryAlpha2 = Annotated[
        StrEnum("CountryAlpha2", [(c, c) for c in ALL_COUNTRIES]),
        WithJsonSchema(
            {
                "type": "string",
                "title": "CountryAlpha2",
                "enum": ALL_COUNTRIES,
            }
        ),
    ]
    CountryAlpha2Input = Annotated[
        StrEnum(
            "CountryAlpha2Input",
            [(c, c) for c in SUPPORTED_COUNTRIES],
        ),
        WithJsonSchema(
            {
                "type": "string",
                "title": "CountryAlpha2Input",
                "enum": SUPPORTED_COUNTRIES,
            }
        ),
    ]


# ── Subdivisions ─────────────────────────────────────────────────────


class USState(StrEnum):
    US_AL = "US-AL"
    US_AK = "US-AK"
    US_AZ = "US-AZ"
    US_AR = "US-AR"
    US_CA = "US-CA"
    US_CO = "US-CO"
    US_CT = "US-CT"
    US_DE = "US-DE"
    US_FL = "US-FL"
    US_GA = "US-GA"
    US_HI = "US-HI"
    US_ID = "US-ID"
    US_IL = "US-IL"
    US_IN = "US-IN"
    US_IA = "US-IA"
    US_KS = "US-KS"
    US_KY = "US-KY"
    US_LA = "US-LA"
    US_ME = "US-ME"
    US_MD = "US-MD"
    US_MA = "US-MA"
    US_MI = "US-MI"
    US_MN = "US-MN"
    US_MS = "US-MS"
    US_MO = "US-MO"
    US_MT = "US-MT"
    US_NE = "US-NE"
    US_NV = "US-NV"
    US_NH = "US-NH"
    US_NJ = "US-NJ"
    US_NM = "US-NM"
    US_NY = "US-NY"
    US_NC = "US-NC"
    US_ND = "US-ND"
    US_OH = "US-OH"
    US_OK = "US-OK"
    US_OR = "US-OR"
    US_PA = "US-PA"
    US_RI = "US-RI"
    US_SC = "US-SC"
    US_SD = "US-SD"
    US_TN = "US-TN"
    US_TX = "US-TX"
    US_UT = "US-UT"
    US_VT = "US-VT"
    US_VA = "US-VA"
    US_WA = "US-WA"
    US_WV = "US-WV"
    US_WI = "US-WI"
    US_WY = "US-WY"
    US_DC = "US-DC"


class CAProvince(StrEnum):
    CA_AB = "CA-AB"
    CA_BC = "CA-BC"
    CA_MB = "CA-MB"
    CA_NB = "CA-NB"
    CA_NL = "CA-NL"
    CA_NS = "CA-NS"
    CA_ON = "CA-ON"
    CA_PE = "CA-PE"
    CA_QC = "CA-QC"
    CA_SK = "CA-SK"


# Countries whose subdivisions must be ISO 3166-2 prefixed (e.g. "US-CA").
_PREFIXED_SUBDIVISION_COUNTRIES: frozenset[str] = frozenset({"US", "CA"})


# ── Typed dict ───────────────────────────────────────────────────────


class AddressDict(TypedDict):
    line1: NotRequired[str]
    line2: NotRequired[str]
    postal_code: NotRequired[str]
    city: NotRequired[str]
    state: NotRequired[str]
    country: str


# ── Pydantic model ───────────────────────────────────────────────────


class Address(BaseModel):
    """A postal address with optional subdivision (state/province) validation."""

    line1: EmptyStrToNone | None = None
    line2: EmptyStrToNone | None = None
    postal_code: EmptyStrToNone | None = None
    city: EmptyStrToNone | None = None
    state: EmptyStrToNone | None = None
    country: CountryAlpha2 = Field(examples=["US", "SE", "FR"])

    # ── Validation ──

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.state is None:
            return self

        # Normalize subdivisions for countries requiring ISO prefix
        if self.country in _PREFIXED_SUBDIVISION_COUNTRIES:
            prefix = f"{self.country}-"
            if not self.state.startswith(prefix):
                self.state = f"{prefix}{self.state}"

        # Validate subdivision codes
        if self.country == "US" and self.state not in USState:
            raise ValueError("Invalid US state")
        if self.country == "CA" and self.state not in CAProvince:
            raise ValueError("Invalid CA province")

        return self

    # ── Serialization helpers ──

    def to_dict(self) -> AddressDict:
        return cast(AddressDict, self.model_dump(exclude_none=True))

    @property
    def unprefixed_state(self) -> str | None:
        """Return the state/province code without the country prefix."""
        if self.state is None:
            return None
        if self.country in _PREFIXED_SUBDIVISION_COUNTRIES:
            return self.state.split("-", maxsplit=1)[1]
        return self.state


class AddressInput(Address):
    country: Annotated[CountryAlpha2Input, BeforeValidator(str.upper)] = Field(  # type: ignore
        examples=["US", "SE", "FR"]
    )


# ── SQLAlchemy column type ───────────────────────────────────────────


class AddressType(TypeDecorator[Any]):
    """Stores an ``Address`` as JSONB and reconstitutes it on load."""

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if isinstance(value, Address):
            return value.model_dump(exclude_none=True)
        return value

    def process_result_value(self, value: str | None, dialect: Dialect) -> Any:
        if value is not None:
            return Address.model_validate(value)
        return value
