"""drop projects extension tables (cycle module page estimate relations favorite)

Implements M1.5 of M1_EXECUTION.md. Drops the project-management
submodules that don't survive the engineering-suite framing:
cycle, module, page, estimate (+ estimate_point), work_item_relation,
and user_favorite.

Order matters — child tables with FK references to parent tables go
first, then the parents. Also drops the work_items.estimate_point_id
column whose FK targets project_estimate_points; that column went
out of the model in M1.5.

Revision ID: e5da4a23c32a
Revises: 27ed2e68876f
Create Date: 2026-05-24 22:22:40.409075
"""

from alembic import op

# Rapidly Custom Imports

# revision identifiers, used by Alembic.
revision = "e5da4a23c32a"
down_revision = "27ed2e68876f"
branch_labels: tuple[str] | None = None
depends_on: tuple[str] | None = None


def upgrade() -> None:
    # 1) work_items.estimate_point_id FK + column — must drop the
    #    column before its target table can go.
    with op.batch_alter_table("work_items") as batch:
        batch.drop_constraint(
            "work_items_estimate_point_id_fkey",
            type_="foreignkey",
        )
        batch.drop_index("ix_work_items_estimate_point_id")
        batch.drop_column("estimate_point_id")

    # 2) Join tables (child FKs into the doomed parents).
    op.drop_table("project_cycle_work_items")
    op.drop_table("project_module_work_items")

    # 3) Leaf tables on the estimate side.
    op.drop_table("project_estimate_points")

    # 4) Parents.
    op.drop_table("project_cycles")
    op.drop_table("project_modules")
    op.drop_table("project_pages")
    op.drop_table("project_estimates")

    # 5) work_item_relations is a peer table (FKs into work_items
    #    both sides) — not a child of the projects-extension family
    #    above, but it's in the M1.5 drop list.
    op.drop_table("work_item_relations")

    # 6) user_favorite — peer, FKs to users + (formerly) project /
    #    cycle / module / page / work_item.
    op.drop_table("user_favorites")


def downgrade() -> None:
    # M1.5 is intended as a one-way demolition. Restoring schema is
    # not destructive but the data is gone irretrievably (no backups
    # taken at migration time) — call this out in the runbook before
    # deploying.
    #
    # If a restore is genuinely needed during the M1 window, check
    # out the migrations that originally created these tables and
    # re-run their upgrade bodies inline here:
    #
    #   2026-05-10-2123_add_projects_domain_tables.py  → estimates
    #   2026-05-10-2245_add_work_item_comment_and_relation_.py
    #     → work_item_relations
    #   2026-05-12-1939_add_project_cycle_tables.py   → cycles
    #   2026-05-12-2008_add_project_module_tables.py  → modules
    #   2026-05-12-2140_add_project_pages.py          → pages
    #   (no separate user_favorites migration — created in the same
    #   commit as the favorite submodule)
    #
    # Keeping this body empty rather than copy-pasting hundreds of
    # lines that may go further stale.
    raise NotImplementedError(
        "M1.5 demolition is one-way. To restore, check out the "
        "originating migrations and re-run their upgrade bodies."
    )
