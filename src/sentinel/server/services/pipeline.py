from __future__ import annotations


class PipelineNotImplementedError(RuntimeError):
    pass


def regenerate_project(*, projectId: str, uploadId: str | None) -> dict:  # noqa: ARG001
    raise PipelineNotImplementedError("Pipeline orchestration is not implemented in server MVP skeleton yet.")

