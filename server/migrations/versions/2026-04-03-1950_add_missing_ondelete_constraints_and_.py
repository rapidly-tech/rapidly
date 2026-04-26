"""add missing ondelete constraints and session limit

Revision ID: 94654a5645a5
Revises: d889e389c54b
Create Date: 2026-04-03 19:50:11.335076

"""

from alembic import op

# Rapidly Custom Imports

# revision identifiers, used by Alembic.
revision = "94654a5645a5"
down_revision = "d889e389c54b"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    # events: add ondelete="set null" to nullable FK columns
    op.drop_constraint(op.f("events_root_id_fkey"), "events", type_="foreignkey")
    op.drop_constraint(op.f("events_customer_id_fkey"), "events", type_="foreignkey")
    op.drop_constraint(op.f("events_event_type_id_fkey"), "events", type_="foreignkey")
    op.drop_constraint(op.f("events_parent_id_fkey"), "events", type_="foreignkey")
    op.create_foreign_key(
        op.f("events_parent_id_fkey"),
        "events",
        "events",
        ["parent_id"],
        ["id"],
        ondelete="set null",
    )
    op.create_foreign_key(
        op.f("events_customer_id_fkey"),
        "events",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="set null",
    )
    op.create_foreign_key(
        op.f("events_event_type_id_fkey"),
        "events",
        "event_types",
        ["event_type_id"],
        ["id"],
        ondelete="set null",
    )
    op.create_foreign_key(
        op.f("events_root_id_fkey"),
        "events",
        "events",
        ["root_id"],
        ["id"],
        ondelete="set null",
    )

    # oauth2_clients: add ondelete="set null" to user_id
    op.drop_constraint(
        op.f("oauth2_clients_user_id_fkey"), "oauth2_clients", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("oauth2_clients_user_id_fkey"),
        "oauth2_clients",
        "users",
        ["user_id"],
        ["id"],
        ondelete="set null",
    )

    # user_notifications: add ondelete="cascade" to user_id
    op.drop_constraint(
        op.f("user_notifications_user_id_fkey"),
        "user_notifications",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("user_notifications_user_id_fkey"),
        "user_notifications",
        "users",
        ["user_id"],
        ["id"],
        ondelete="cascade",
    )

    # workspace_access_tokens: add ondelete="cascade" to workspace_id
    op.drop_constraint(
        op.f("workspace_access_tokens_workspace_id_fkey"),
        "workspace_access_tokens",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("workspace_access_tokens_workspace_id_fkey"),
        "workspace_access_tokens",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="cascade",
    )

    # workspace_memberships: add ondelete="cascade" to user_id
    op.drop_constraint(
        op.f("workspace_memberships_user_id_fkey"),
        "workspace_memberships",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("workspace_memberships_user_id_fkey"),
        "workspace_memberships",
        "users",
        ["user_id"],
        ["id"],
        ondelete="cascade",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("workspace_memberships_user_id_fkey"),
        "workspace_memberships",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("workspace_memberships_user_id_fkey"),
        "workspace_memberships",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_constraint(
        op.f("workspace_access_tokens_workspace_id_fkey"),
        "workspace_access_tokens",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("workspace_access_tokens_workspace_id_fkey"),
        "workspace_access_tokens",
        "workspaces",
        ["workspace_id"],
        ["id"],
    )

    op.drop_constraint(
        op.f("user_notifications_user_id_fkey"),
        "user_notifications",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("user_notifications_user_id_fkey"),
        "user_notifications",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_constraint(
        op.f("oauth2_clients_user_id_fkey"), "oauth2_clients", type_="foreignkey"
    )
    op.create_foreign_key(
        op.f("oauth2_clients_user_id_fkey"),
        "oauth2_clients",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_constraint(op.f("events_root_id_fkey"), "events", type_="foreignkey")
    op.drop_constraint(op.f("events_event_type_id_fkey"), "events", type_="foreignkey")
    op.drop_constraint(op.f("events_customer_id_fkey"), "events", type_="foreignkey")
    op.drop_constraint(op.f("events_parent_id_fkey"), "events", type_="foreignkey")
    op.create_foreign_key(
        op.f("events_parent_id_fkey"), "events", "events", ["parent_id"], ["id"]
    )
    op.create_foreign_key(
        op.f("events_event_type_id_fkey"),
        "events",
        "event_types",
        ["event_type_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("events_customer_id_fkey"),
        "events",
        "customers",
        ["customer_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("events_root_id_fkey"), "events", "events", ["root_id"], ["id"]
    )
