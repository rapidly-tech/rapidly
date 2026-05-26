"""Auth dependencies for VectorCollection routes.

Read scope is permissive (a workflow editor needs to populate a
node's ``collection_id`` field). Write scope is admin-only because
mutations either change tenant data or spend embedding-API budget
(the /index trigger).
"""

from typing import Annotated

from fastapi import Depends

from rapidly.identity.auth.dependencies import Authenticator
from rapidly.identity.auth.models import AuthPrincipal, User, Workspace
from rapidly.identity.auth.scope import Scope

_VectorCollectionsRead = Authenticator(
    required_scopes={
        Scope.web_read,
        Scope.web_write,
        Scope.vector_collections_read,
        Scope.vector_collections_write,
    },
    allowed_subjects={User, Workspace},
)
VectorCollectionsRead = Annotated[
    AuthPrincipal[User | Workspace], Depends(_VectorCollectionsRead)
]

_VectorCollectionsWrite = Authenticator(
    required_scopes={Scope.web_write, Scope.vector_collections_write},
    allowed_subjects={User, Workspace},
)
VectorCollectionsWrite = Annotated[
    AuthPrincipal[User | Workspace], Depends(_VectorCollectionsWrite)
]
