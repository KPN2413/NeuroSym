from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from verilogic_ns_api.orchestration.errors import QueueFullError, UnknownRunError
from verilogic_ns_api.orchestration.models import (
    ApiErrorResponse,
    CapabilitiesResponse,
    InputMode,
    PipelineRequest,
    PipelineRunAccepted,
    PipelineRunState,
    PolicyMode,
    ProviderMode,
)
from verilogic_ns_api.reasoning.configuration import ReasoningLimits

router = APIRouter(prefix="/api/v1/neurosymbolic", tags=["neurosymbolic"])


@router.post(
    "/runs",
    response_model=PipelineRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        422: {"model": ApiErrorResponse},
        429: {"model": ApiErrorResponse},
        503: {"model": ApiErrorResponse},
    },
)
def submit_run(payload: PipelineRequest, request: Request) -> PipelineRunAccepted:
    factory = request.app.state.orchestration_factory
    if (
        payload.input_mode is InputMode.NATURAL_LANGUAGE
        and factory.provider_mode is ProviderMode.LIVE
        and not factory.model_ready()
    ):
        raise HTTPException(
            status_code=503,
            detail=ApiErrorResponse(
                code="LOCAL_MODEL_UNAVAILABLE",
                message="The exact local Ollama model is not ready.",
            ).model_dump(mode="json"),
        )
    try:
        return request.app.state.job_manager.submit(payload)
    except QueueFullError as error:
        raise HTTPException(
            status_code=429,
            detail=ApiErrorResponse(
                code="QUEUE_FULL",
                message="The bounded local inference queue is full.",
            ).model_dump(mode="json"),
        ) from error


@router.get(
    "/runs/{run_id}",
    response_model=PipelineRunState,
    responses={404: {"model": ApiErrorResponse}},
)
def get_run(run_id: str, request: Request) -> PipelineRunState:
    try:
        return request.app.state.job_manager.get(run_id)
    except UnknownRunError as error:
        raise HTTPException(
            status_code=404,
            detail=ApiErrorResponse(
                code="RUN_NOT_FOUND",
                message="The run is unknown or has expired.",
            ).model_dump(mode="json"),
        ) from error


@router.delete(
    "/runs/{run_id}",
    response_model=PipelineRunState,
    responses={404: {"model": ApiErrorResponse}},
)
def cancel_run(run_id: str, request: Request) -> PipelineRunState:
    try:
        return request.app.state.job_manager.cancel(run_id)
    except UnknownRunError as error:
        raise HTTPException(
            status_code=404,
            detail=ApiErrorResponse(
                code="RUN_NOT_FOUND",
                message="The run is unknown or has expired.",
            ).model_dump(mode="json"),
        ) from error


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities(request: Request) -> CapabilitiesResponse:
    factory = request.app.state.orchestration_factory
    frozen = factory.frozen
    runtime = frozen.parser_config.runtime
    limits = ReasoningLimits()
    return CapabilitiesResponse(
        supported_input_modes=tuple(InputMode),
        supported_policy_modes=tuple(PolicyMode),
        symbolic_engine_ready=True,
        local_model_ready=factory.model_ready(),
        provider_mode=factory.provider_mode,
        model_name=runtime.model,
        model_digest=runtime.model_digest,
        provider_version=runtime.provider_version,
        maximum_queued_jobs=request.app.state.job_manager.maximum_queued_jobs,
        resource_limits=limits.as_dict(),
        schema_hashes=frozen.schema_hashes,
    )
