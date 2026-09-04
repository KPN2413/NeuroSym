from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from verilogic_ns_api.research_frontend.ast_inspection import inspect_ast
from verilogic_ns_api.research_frontend.catalogue import ResearchCatalogueService
from verilogic_ns_api.research_frontend.exports import render_export, select_experiments
from verilogic_ns_api.research_frontend.models import (
    AstInspectionRequest,
    CatalogueOverview,
    ComparisonCompatibility,
    ExperimentDetail,
    ExperimentListResponse,
    NormalizedAstInspection,
    ResearchApiError,
    ResearchDashboardSnapshot,
)

router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _service(request: Request) -> ResearchCatalogueService:
    return request.app.state.research_catalogue


def _not_found(message: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=ResearchApiError(code="RESEARCH_EVIDENCE_NOT_FOUND", message=message).model_dump(
            mode="json"
        ),
    )


@router.get("/catalogue", response_model=CatalogueOverview)
def catalogue(request: Request) -> CatalogueOverview:
    """Return the validated, aggregate catalogue overview."""
    return _service(request).overview()


@router.get("/dashboard", response_model=ResearchDashboardSnapshot)
def dashboard(request: Request) -> ResearchDashboardSnapshot:
    """Return the complete validated dashboard bootstrap in one request."""
    return _service(request).dashboard()


@router.get("/experiments", response_model=ExperimentListResponse)
def list_experiments(
    request: Request,
    phase: Annotated[str | None, Query(max_length=40)] = None,
    condition: Annotated[str | None, Query(max_length=80)] = None,
    policy_mode: Annotated[str | None, Query(max_length=80)] = None,
    model: Annotated[str | None, Query(max_length=160)] = None,
    dataset: Annotated[str | None, Query(max_length=100)] = None,
    split: Annotated[str | None, Query(max_length=80)] = None,
    status: Annotated[str | None, Query(max_length=80)] = None,
    comparability_group: Annotated[str | None, Query(max_length=128)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ExperimentListResponse:
    filters = {
        key: value
        for key, value in {
            "phase": phase,
            "condition": condition,
            "policy_mode": policy_mode,
            "model": model,
            "dataset": dataset,
            "split": split,
            "status": status,
            "comparability_group": comparability_group,
        }.items()
        if value is not None
    }
    service = _service(request)
    selected = select_experiments(service, filters)
    start = (page - 1) * page_size
    return ExperimentListResponse(
        items=tuple(service.summary(item) for item in selected[start : start + page_size]),
        total=len(selected),
        page=page,
        page_size=page_size,
    )


@router.get(
    "/experiments/{experiment_id}",
    response_model=ExperimentDetail,
    responses={404: {"model": ResearchApiError}},
)
def experiment(experiment_id: str, request: Request) -> ExperimentDetail:
    evidence = _service(request).experiment(experiment_id)
    if evidence is None:
        raise _not_found("The requested experiment is not in the evidence catalogue.")
    return evidence


@router.get("/comparisons", response_model=tuple[ComparisonCompatibility, ...])
def comparisons(request: Request) -> tuple[ComparisonCompatibility, ...]:
    return _service(request).catalogue.comparisons


def _render_export_response(
    request: Request,
    export_format: Literal["json", "csv", "markdown"],
    phase: str | None,
    condition: str | None,
    policy_mode: str | None,
) -> Response:
    filters = {
        key: value
        for key, value in {
            "phase": phase,
            "condition": condition,
            "policy_mode": policy_mode,
        }.items()
        if value is not None
    }
    rendered = render_export(_service(request), export_format, filters)
    return Response(
        content=rendered.content,
        media_type=rendered.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{rendered.manifest.filename}"',
            "X-Evidence-Content-SHA256": rendered.manifest.canonical_content_hash,
        },
    )


@router.get("/exports")
def aggregate_export(
    request: Request,
    export_format: Annotated[Literal["json", "csv", "markdown"], Query(alias="format")] = "json",
    phase: Annotated[str | None, Query(max_length=40)] = None,
    condition: Annotated[str | None, Query(max_length=80)] = None,
    policy_mode: Annotated[str | None, Query(max_length=80)] = None,
) -> Response:
    return _render_export_response(request, export_format, phase, condition, policy_mode)


@router.get("/exports/{export_format}", include_in_schema=False)
def aggregate_export_path(
    export_format: Literal["json", "csv", "markdown"],
    request: Request,
    phase: Annotated[str | None, Query(max_length=40)] = None,
    condition: Annotated[str | None, Query(max_length=80)] = None,
    policy_mode: Annotated[str | None, Query(max_length=80)] = None,
) -> Response:
    return _render_export_response(request, export_format, phase, condition, policy_mode)


@router.post("/ast-inspect", response_model=NormalizedAstInspection)
def ast_inspection(payload: AstInspectionRequest) -> NormalizedAstInspection:
    """Render a supplied accepted AST without invoking a model or solver."""
    return inspect_ast(payload)
