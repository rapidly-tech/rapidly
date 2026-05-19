"""HTTP routes for work-item attachments."""

from uuid import UUID

from fastapi import Depends, Query

from rapidly.core.pagination import PaginatedList, PaginationParamsQuery
from rapidly.errors import ResourceNotFound
from rapidly.openapi import APITag
from rapidly.postgres import (
    AsyncReadSession,
    AsyncSession,
    get_db_read_session,
    get_db_session,
)
from rapidly.projects.attachment import actions as attachment_actions
from rapidly.projects.attachment import ordering
from rapidly.projects.attachment import permissions as auth
from rapidly.projects.attachment import types as schemas
from rapidly.routing import APIRouter

router = APIRouter(
    prefix="/work-item-attachments", tags=["work-item-attachments", APITag.public]
)


@router.get(
    "/",
    summary="List Work Item Attachments",
    response_model=PaginatedList[schemas.WorkItemAttachment],
)
async def list(
    auth_subject: auth.WorkItemAttachmentsRead,
    pagination: PaginationParamsQuery,
    sorting: ordering.WorkItemAttachmentsSorting,
    session: AsyncReadSession = Depends(get_db_read_session),
    work_item_id: UUID = Query(
        ..., description="Required filter; returns attachments for this work item."
    ),
) -> PaginatedList[schemas.WorkItemAttachment]:
    results, count = await attachment_actions.list_for_work_item(
        session,
        auth_subject,
        work_item_id=work_item_id,
        pagination=pagination,
        sorting=sorting,
    )
    return PaginatedList.from_paginated_results(
        [schemas.WorkItemAttachment.model_validate(a) for a in results],
        count,
        pagination,
    )


@router.get(
    "/{id}",
    summary="Get Work Item Attachment",
    response_model=schemas.WorkItemAttachment,
    responses={404: {}},
)
async def get(
    id: schemas.WorkItemAttachmentID,
    auth_subject: auth.WorkItemAttachmentsRead,
    session: AsyncReadSession = Depends(get_db_read_session),
) -> schemas.WorkItemAttachment:
    attachment = await attachment_actions.get(session, auth_subject, id)
    if attachment is None:
        raise ResourceNotFound()
    return schemas.WorkItemAttachment.model_validate(attachment)


@router.post(
    "/",
    summary="Create Work Item Attachment",
    response_model=schemas.WorkItemAttachment,
    status_code=201,
    responses={400: {}, 404: {}, 409: {}},
)
async def create(
    body: schemas.WorkItemAttachmentCreate,
    auth_subject: auth.WorkItemAttachmentsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> schemas.WorkItemAttachment:
    attachment = await attachment_actions.create(session, auth_subject, body)
    return schemas.WorkItemAttachment.model_validate(attachment)


@router.delete(
    "/{id}",
    summary="Delete Work Item Attachment",
    status_code=204,
    responses={404: {}},
)
async def delete(
    id: schemas.WorkItemAttachmentID,
    auth_subject: auth.WorkItemAttachmentsWrite,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    attachment = await attachment_actions.get(session, auth_subject, id)
    if attachment is None:
        raise ResourceNotFound()
    await attachment_actions.delete(session, auth_subject, attachment)
