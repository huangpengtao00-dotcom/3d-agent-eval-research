from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import ValidationError

from agent_eval.bundle import build_bundle
from agent_eval.canonical import verify_checksum_file
from agent_eval.contracts import BundleManifest, DataQualityStatus, DisclosureClass

app = typer.Typer(no_args_is_help=True)


@app.command()
def bundle(source: Path, output: Path) -> None:
    bundle_path = build_bundle(source, output, DisclosureClass.PRIVATE_REPRODUCIBLE)
    manifest = BundleManifest.model_validate_json(
        (bundle_path / "manifest.json").read_text(encoding="utf-8")
    )
    typer.echo(
        json.dumps(
            {
                "trajectory_id": manifest.trajectory_id,
                "status": manifest.data_quality.status.value,
                "issues": manifest.data_quality.issues,
                "bundle": str(bundle_path),
            },
            sort_keys=True,
        )
    )
    if manifest.data_quality.status is DataQualityStatus.EXCLUDED:
        raise typer.Exit(2)


@app.command()
def audit(bundle_path: Path) -> None:
    failures = verify_checksum_file(bundle_path)
    manifest_path = bundle_path / "manifest.json"
    if failures or not manifest_path.is_file():
        typer.echo(json.dumps({"status": "excluded", "issues": ["bundle_checksum_incomplete"]}))
        raise typer.Exit(2)
    try:
        manifest = BundleManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValidationError):
        typer.echo(json.dumps({"status": "excluded", "issues": ["bundle_checksum_incomplete"]}))
        raise typer.Exit(2) from None
    typer.echo(manifest.data_quality.model_dump_json())
