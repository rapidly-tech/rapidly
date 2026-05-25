"""Auth dependencies for federated-model routes.

Read is project-member territory; create/update/delete is project-
admin. Pattern mirrors ``projects/deploy_board/permissions.py``.
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_FederatedModelsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.federated_models_read,
        Scope.federated_models_write,
    },
    allowed_subjects={User, Workspace},
)
FederatedModelsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_FederatedModelsRead)
]

_FederatedModelsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.federated_models_write},
    allowed_subjects={User, Workspace},
)
FederatedModelsWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_FederatedModelsWrite)
]
