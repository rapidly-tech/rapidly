"""Team section with member listing and management actions."""

import contextlib
from collections.abc import Generator

from fastapi import Request
from tagflow import tag, text

from rapidly.models import User, Workspace
from rapidly.models.workspace_membership import WorkspaceMembership

from ....components import action_bar, button, card

# Requirements shown when an account is connected.
_ADMIN_CHANGE_RULES: list[str] = [
    "No Stripe account connected (restriction for alpha)",
    "New admin must be verified",
    "At least 2 team members required",
]


def _member_initial(email: str | None) -> str:
    """Return the first character of an email for an avatar placeholder."""
    return email[0].upper() if email else "?"


class TeamSection:
    """Render the team section with member management."""

    def __init__(self, workspace: Workspace, admin_user: User | None = None):
        self._workspace = workspace
        self._admin = admin_user

    # Keep `.org` accessible for callers that depend on it
    @property
    def org(self) -> Workspace:
        return self._workspace

    def _is_admin_member(self, user_id: object) -> bool:
        return self._admin is not None and user_id == self._admin.id

    def _render_member_card(
        self, request: Request, member: WorkspaceMembership
    ) -> None:
        """Render a single member row."""
        with tag.div(
            classes="flex items-center justify-between p-4 border border-base-300 rounded-lg hover:bg-base-50"
        ):
            with tag.div(classes="flex items-center gap-4 flex-1"):
                # Avatar circle
                with tag.div(
                    classes="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center"
                ):
                    with tag.span(classes="text-primary font-bold"):
                        text(_member_initial(member.user.email))

                # Name & role
                with tag.div():
                    with tag.div(classes="font-semibold"):
                        text(member.user.email or "Unknown")
                    with tag.div(classes="text-sm text-base-content/60"):
                        role = (
                            "Admin"
                            if self._is_admin_member(member.user_id)
                            else "Member"
                        )
                        joined = member.created_at.strftime("%Y-%m-%d")
                        text(f"{role} · Joined {joined}")

            # Action buttons
            with action_bar(position="right"):
                with button(
                    variant="secondary",
                    size="sm",
                    ghost=True,
                    hx_post=str(request.url_for("admin:start_impersonation")),
                    hx_vals=f'{{"user_id": "{member.user_id}"}}',
                    hx_confirm="Are you sure you want to impersonate this user?",
                ):
                    text("Impersonate")

                self._render_overflow_menu(request, member)

    def _render_overflow_menu(
        self, request: Request, member: WorkspaceMembership
    ) -> None:
        """Three-dot dropdown with admin/remove options."""
        with tag.div(classes="dropdown dropdown-end"):
            with tag.button(
                classes="btn btn-ghost btn-sm",
                **{"aria-label": "More options", "tabindex": "0"},
            ):
                text("\u22ee")  # vertical ellipsis
            with tag.ul(
                classes="dropdown-content menu shadow bg-base-100 rounded-box w-52 z-10",
                **{"tabindex": "0"},
            ):
                if not self._is_admin_member(member.user_id):
                    with tag.li():
                        with tag.a(
                            hx_post=str(
                                request.url_for(
                                    "workspaces-v2:make_admin",
                                    workspace_id=self._workspace.id,
                                    user_id=member.user_id,
                                )
                            ),
                            hx_confirm="Make this user an admin?",
                        ):
                            text("Make Admin")
                with tag.li():
                    with tag.a(
                        hx_delete=str(
                            request.url_for(
                                "workspaces-v2:remove_member",
                                workspace_id=self._workspace.id,
                                user_id=member.user_id,
                            )
                        ),
                        hx_confirm="Remove this member?",
                        classes="text-error",
                    ):
                        text("Remove Member")

    @contextlib.contextmanager
    def render(self, request: Request) -> Generator[None]:
        with tag.div(classes="space-y-6"):
            with card(bordered=True):
                with tag.div(classes="mb-4"):
                    with tag.h2(classes="text-lg font-bold"):
                        text("Team Members")

                members = getattr(self._workspace, "members", None)
                if members:
                    with tag.div(classes="space-y-3"):
                        for m in members:
                            self._render_member_card(request, m)
                else:
                    with tag.div(classes="text-center py-8 text-base-content/60"):
                        text("No team members found")

            # Admin-change rules (only relevant if account exists)
            if hasattr(self._workspace, "account") and self._workspace.account:
                with card(bordered=True):
                    with tag.h3(classes="text-md font-bold mb-3"):
                        text("Admin Change Requirements")
                    with tag.ul(classes="space-y-2 text-sm"):
                        for rule in _ADMIN_CHANGE_RULES:
                            with tag.li(classes="flex items-start gap-2"):
                                with tag.span(classes="text-base-content/60"):
                                    text(f"\u2022 {rule}")

            yield


__all__ = ["TeamSection"]
