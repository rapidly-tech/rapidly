"""Payment method persistence layer with customer-scoped queries."""

from uuid import UUID

from sqlalchemy import Select, select

from rapidly.core.queries import (
    Options,
    Repository,
    SoftDeleteByIdMixin,
    SoftDeleteMixin,
)
from rapidly.enums import PaymentProcessor
from rapidly.models.payment_method import PaymentMethod


class PaymentMethodRepository(
    SoftDeleteByIdMixin[PaymentMethod, UUID],
    SoftDeleteMixin[PaymentMethod],
    Repository[PaymentMethod],
):
    """Payment method queries scoped to customers."""

    model = PaymentMethod

    async def get_by_customer_and_processor_id(
        self,
        customer_id: UUID,
        processor: PaymentProcessor,
        processor_id: str,
        *,
        include_deleted: bool = False,
        options: Options = (),
    ) -> PaymentMethod | None:
        stmt = (
            self._base_stmt(include_deleted)
            .where(
                PaymentMethod.customer_id == customer_id,
                PaymentMethod.processor == processor,
                PaymentMethod.processor_id == processor_id,
            )
            .options(*options)
        )
        return await self.get_one_or_none(stmt)

    async def list_by_customer(
        self,
        customer_id: UUID,
        *,
        options: Options = (),
    ) -> list[PaymentMethod]:
        stmt = (
            self.get_base_statement()
            .where(PaymentMethod.customer_id == customer_id)
            .order_by(PaymentMethod.created_at.desc())
            .options(*options)
        )
        return list(await self.get_all(stmt))

    def _base_stmt(self, include_deleted: bool) -> Select[tuple[PaymentMethod]]:
        if include_deleted:
            return select(PaymentMethod)
        return self.get_base_statement()
