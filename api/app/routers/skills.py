"""Skill-related API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from ..deps import InferenceDep, SettingsDep
from ..errors import InferenceUnavailable
from ..schemas import (
    ErrorResponse,
    EvaluateRequest,
    EvaluationReport,
    GenerateRequest,
    GenerateResponse,
    Skill,
    ValidateRequest,
    ValidationReport,
)
from ..services import exporter, generator, samples
from ..services.evaluator import evaluate_skill
from ..services.validator import validate_skill

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("/sample", response_model=GenerateResponse, summary="Bundled sample skill (no credentials needed)")
def sample_skill() -> GenerateResponse:
    skill = samples.get_sample_skill()
    report = validate_skill(skill, expected_root=samples.SAMPLE_SKILL_NAME)
    return GenerateResponse(skill=skill, validation=report, model="sample", usage=None, warnings=[])


@router.post(
    "/validate",
    response_model=ValidationReport,
    summary="Deterministically validate a skill against the Agent Skills standard",
)
def validate(request: ValidateRequest) -> ValidationReport:
    return validate_skill(request.skill, expected_root=request.expected_root)


@router.post(
    "/generate",
    response_model=GenerateResponse,
    responses={503: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    summary="Generate a skill with DigitalOcean Inference",
)
async def generate(request: GenerateRequest, client: InferenceDep, settings: SettingsDep) -> GenerateResponse:
    if client is None:
        raise InferenceUnavailable(
            "DIGITALOCEAN_INFERENCE_KEY is not configured on the server, so AI generation is unavailable. "
            "Set it in the backend environment to enable generation, or explore the bundled sample skill."
        )
    return await generator.generate_skill(
        request,
        client,
        max_files=settings.max_files,
        max_total_bytes=settings.max_total_bytes,
    )


@router.post(
    "/evaluate",
    response_model=EvaluationReport,
    responses={503: {"model": ErrorResponse}},
    summary="Evaluate a skill against user-defined scenarios",
)
async def evaluate(request: EvaluateRequest, client: InferenceDep) -> EvaluationReport:
    return await evaluate_skill(request, client)


@router.post(
    "/export",
    summary="Download a skill package as a ZIP with the correct directory structure",
    responses={422: {"model": ErrorResponse}},
)
def export(request: ValidateRequest, settings: SettingsDep) -> Response:
    data, root = exporter.build_zip(
        request.skill,
        max_files=settings.max_files,
        max_total_bytes=settings.max_total_bytes,
    )
    headers = {"Content-Disposition": f'attachment; filename="{root}.zip"'}
    return Response(content=data, media_type="application/zip", headers=headers)


@router.post(
    "/import",
    response_model=Skill,
    summary="Safely import a skill from a ZIP archive",
    responses={413: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def import_skill(request: Request, settings: SettingsDep) -> Skill:
    data = await request.body()
    if not data:
        raise HTTPException(status_code=422, detail="Empty request body; expected a ZIP archive.")
    if len(data) > settings.max_total_bytes + 64 * 1024:
        raise HTTPException(status_code=413, detail="Uploaded archive is too large.")
    return exporter.safe_extract_zip(
        data,
        max_files=settings.max_files,
        max_total_bytes=settings.max_total_bytes,
    )
