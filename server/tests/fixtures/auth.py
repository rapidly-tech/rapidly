"""Authentication subject fixtures and test parametrization helpers."""

from typing import Any, Literal

import pytest

from rapidly.identity.auth.models import Anonymous, AuthPrincipal, Subject
from rapidly.identity.auth.scope import Scope
from rapidly.models import Customer, Member, User, Workspace

# ── Auth subject configuration ──


class AuthSubjectFixture:
    def __init__(
        self,
        *,
        subject: Literal[
            "anonymous",
            "user",
            "user_second",
            "workspace",
            "workspace_second",
            "customer",
            "member_owner",
            "member_billing_manager",
            "member",
        ] = "user",
        scopes: set[Scope] = {Scope.web_read, Scope.web_write},
    ):
        self.subject = subject
        self.scopes = scopes

    def __repr__(self) -> str:
        scopes = (
            "{" + ", ".join(repr(scope.value) for scope in sorted(self.scopes)) + "}"
        )
        return f"AuthSubjectFixture(subject={self.subject!r}, scopes={scopes})"


# ── Predefined auth subject constants ──


CUSTOMER_AUTH_SUBJECT = AuthSubjectFixture(
    subject="customer", scopes={Scope.customer_portal_read, Scope.customer_portal_write}
)

MEMBER_OWNER_AUTH_SUBJECT = AuthSubjectFixture(
    subject="member_owner",
    scopes={Scope.customer_portal_read, Scope.customer_portal_write},
)

MEMBER_BILLING_MANAGER_AUTH_SUBJECT = AuthSubjectFixture(
    subject="member_billing_manager",
    scopes={Scope.customer_portal_read, Scope.customer_portal_write},
)

MEMBER_AUTH_SUBJECT = AuthSubjectFixture(
    subject="member",
    scopes={Scope.customer_portal_read, Scope.customer_portal_write},
)


# ── Fixtures ──


@pytest.fixture
def auth_subject(
    request: pytest.FixtureRequest,
    user: User,
    user_second: User,
    workspace: Workspace,
    workspace_second: Workspace,
    customer: Customer,
) -> AuthPrincipal[Subject]:
    """
    This fixture generates an AuthPrincipal instance used by the `client` fixture
    to override the FastAPI authentication dependency, but also can be used manually
    if needed.

    Its parameters are generated through the `auth` marker.
    See `pytest_generate_tests` below for more information.
    """
    auth_subject_fixture: AuthSubjectFixture = request.param

    # Build subjects map, loading member lazily only when needed
    subjects_map: dict[str, Anonymous | Customer | Member | User | Workspace] = {
        "anonymous": Anonymous(),
        "user": user,
        "user_second": user_second,
        "workspace": workspace,
        "workspace_second": workspace_second,
        "customer": customer,
    }

    # Only load member fixtures when actually needed to avoid creating
    # extra Member records that pollute member count tests
    subject_key = auth_subject_fixture.subject
    if subject_key == "member":
        member: Member = request.getfixturevalue("member")
        subjects_map["member"] = member
    elif subject_key == "member_owner":
        member_owner: Member = request.getfixturevalue("member_owner")
        subjects_map["member_owner"] = member_owner
    elif subject_key == "member_billing_manager":
        member_billing_manager: Member = request.getfixturevalue(
            "member_billing_manager"
        )
        subjects_map["member_billing_manager"] = member_billing_manager

    return AuthPrincipal(subjects_map[subject_key], auth_subject_fixture.scopes, None)


# ── Test parametrization ──


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    # The test requests the `auth_subject` fixture
    if "auth_subject" in metafunc.fixturenames:
        pytest_params = []

        # The test is decorated with the `auth` marker
        auth_marker = metafunc.definition.get_closest_marker("auth")
        if auth_marker is not None:
            # No argument: use a default AuthSubjectFixture
            args: tuple[Any] = auth_marker.args
            if len(args) == 0:
                args = (AuthSubjectFixture(),)

            # Generate a test for each AuthSubjectFixture argument
            for arg in args:
                if not isinstance(arg, AuthSubjectFixture):
                    raise ValueError(
                        "auth marker arguments must be "
                        f"of type AuthSubjectFixture, got {type(arg)}"
                    )
                pytest_params.append(pytest.param(arg, id=repr(arg)))
        # Test is not decorated with `auth` marker: consider the user anonymous
        else:
            pytest_params = [
                pytest.param(AuthSubjectFixture(subject="anonymous"), id="anonymous")
            ]
        metafunc.parametrize("auth_subject", pytest_params, indirect=["auth_subject"])
