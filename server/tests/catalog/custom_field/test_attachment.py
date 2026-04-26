"""Tests for ``rapidly/catalog/custom_field/attachment.py``.

Auto-tracking registry for custom-field attachment association
tables. Four load-bearing surfaces:

- The ``mapper_configured`` event auto-registers EVERY concrete
  subclass of ``AttachedCustomFieldMixin``. Drift to drop the
  registration would break ``CustomFieldRepository.delete_attachments``
  cascade — orphaned attachment rows would later trigger FK
  violations.
- Every registered model declares the documented columns:
  ``custom_field_id`` (UUID PK + FK), ``order`` (int, indexed),
  ``required`` (bool, default False). Drift on these would
  break the share-detail page custom-field renderer.
- ``custom_field_id`` FK uses ``ondelete="cascade"`` — drift
  would orphan attachment rows when the underlying custom
  field is hard-deleted at the DB level.
- ``required`` defaults to False — drift to True would mark
  every newly-attached field as mandatory and 422 every form
  submission that hadn't been updated yet.
"""

from __future__ import annotations

# Importing rapidly.models forces the SQLAlchemy mappers to
# configure, which populates the auto-tracking registry.
import rapidly.models  # noqa: F401
from rapidly.catalog.custom_field.attachment import (
    AttachedCustomFieldMixin,
    attached_custom_fields_models,
)


class TestRegistryNonEmpty:
    def test_registry_populated_after_imports(self) -> None:
        # Pin: at least ONE concrete model is registered. Drift
        # to a registry of zero would break the cascade-delete
        # path in CustomFieldRepository.delete_attachments
        # silently.
        assert len(attached_custom_fields_models) > 0

    def test_every_registered_model_subclasses_the_mixin(self) -> None:
        # Pin: the auto-tracking event ONLY adds subclasses (no
        # accidental garbage). Drift to a wider event filter
        # would let unrelated models pollute the cascade.
        for model in attached_custom_fields_models:
            assert issubclass(model, AttachedCustomFieldMixin), model


class TestColumnContract:
    def test_every_model_declares_custom_field_id_column(self) -> None:
        # Pin: PK + FK column on every attachment model.
        for model in attached_custom_fields_models:
            assert hasattr(model, "custom_field_id"), model

    def test_every_model_declares_order_column(self) -> None:
        # Pin: ordering column on every attachment model so the
        # share-detail page renders fields in the configured
        # sequence.
        for model in attached_custom_fields_models:
            assert hasattr(model, "order"), model

    def test_every_model_declares_required_column(self) -> None:
        # Pin: required-flag on every attachment model.
        for model in attached_custom_fields_models:
            assert hasattr(model, "required"), model

    def test_required_default_is_false(self) -> None:
        # Pin: drift to True would mark every newly-attached
        # field as mandatory and 422 every form submission that
        # hadn't been updated yet.
        # The default is on the mapped_column descriptor — read
        # via the SQLAlchemy column.
        from sqlalchemy import inspect as sa_inspect

        for model in attached_custom_fields_models:
            mapper = sa_inspect(model)
            assert mapper is not None
            required_col = mapper.columns["required"]
            assert required_col.default is not None
            # ``ColumnDefault.arg`` is the literal default value.
            assert required_col.default.arg is False, model


class TestForeignKeyCascade:
    def test_custom_field_id_fk_uses_cascade_on_delete(self) -> None:
        # Pin: ``ondelete="cascade"`` so that a hard-deleted
        # custom field's attachment rows are removed AT THE DB
        # LEVEL too. Drift would orphan attachment rows that
        # reference a non-existent custom_field_id, breaking
        # subsequent JOINs.
        from sqlalchemy import inspect as sa_inspect

        for model in attached_custom_fields_models:
            mapper = sa_inspect(model)
            assert mapper is not None
            cf_col = mapper.columns["custom_field_id"]
            # The column has at least one ForeignKey.
            assert cf_col.foreign_keys, model
            for fk in cf_col.foreign_keys:
                assert fk.ondelete is not None, model
                assert fk.ondelete.lower() == "cascade", (model, fk.ondelete)
