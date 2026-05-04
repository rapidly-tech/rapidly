"""Share-price type guards for discriminating price variants."""

from typing_extensions import TypeIs

from rapidly.models.share_price import (
    SharePrice,
    SharePriceCustom,
    SharePriceFixed,
    SharePriceFree,
)

type StaticPrice = SharePriceFixed | SharePriceFree | SharePriceCustom
type FixedPrice = SharePriceFixed
type CustomPrice = SharePriceCustom
type FreePrice = SharePriceFree


def is_fixed_price(price: SharePrice) -> TypeIs[FixedPrice]:
    return isinstance(price, SharePriceFixed)


def is_custom_price(price: SharePrice) -> TypeIs[CustomPrice]:
    return isinstance(price, SharePriceCustom)


def is_free_price(price: SharePrice) -> TypeIs[FreePrice]:
    return isinstance(price, SharePriceFree)


def is_static_price(price: SharePrice) -> TypeIs[StaticPrice]:
    return price.is_static
