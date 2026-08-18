from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from verilogic_ns_api.research_frontend.catalogue import (
    CatalogueIntegrityError,
    ResearchCatalogueService,
    write_seed_catalogue,
)
from verilogic_ns_api.research_frontend.exports import render_export
from verilogic_ns_api.research_frontend.schema_export import export_schemas, schema_hashes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verilogic-research-frontend",
        description="Validate and export the evidence-backed Phase 8 research catalogue.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-catalogue", help="Validate catalogue models and source hashes")
    commands.add_parser("catalogue-summary", help="Print a sanitized aggregate summary")
    build = commands.add_parser(
        "build-catalogue", help="Build the tracked catalogue deterministically"
    )
    build.add_argument("--check", action="store_true")
    schemas = commands.add_parser("export-schemas", help="Export versioned research schemas")
    schemas.add_argument("--check", action="store_true")
    export = commands.add_parser("export", help="Write a deterministic aggregate export")
    export.add_argument("--format", choices=("json", "csv", "markdown"), required=True)
    export.add_argument("--output-directory", type=Path, default=Path("results/research-exports"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "build-catalogue":
            path = write_seed_catalogue(check=args.check)
            print(path.as_posix())
            return 0
        if args.command == "export-schemas":
            export_schemas(check=args.check)
            print(json.dumps(schema_hashes(), indent=2, sort_keys=True))
            return 0
        service = ResearchCatalogueService()
        if args.command == "validate-catalogue":
            print(
                json.dumps(
                    {
                        "status": "VERIFIED",
                        "catalogue_hash": service.catalogue.canonical_hash,
                        "experiments": len(service.catalogue.experiments),
                        "comparisons": len(service.catalogue.comparisons),
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "catalogue-summary":
            print(service.overview().model_dump_json(indent=2))
            return 0
        rendered = render_export(service, args.format)
        root = Path.cwd().resolve()
        directory = args.output_directory.resolve()
        if not directory.is_relative_to(root):
            raise ValueError("output directory must remain beneath the repository")
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / rendered.manifest.filename
        target.write_bytes(rendered.content)
        print(target.as_posix())
        return 0
    except (CatalogueIntegrityError, OSError, RuntimeError, ValueError) as error:
        print(f"Research catalogue command failed safely: {type(error).__name__}", file=sys.stderr)
        return 2
