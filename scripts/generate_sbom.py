#!/usr/bin/env python3
"""Generate an SPDX 2.3 JSON inventory for the frozen app bundle."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_APP = ROOT / "dist" / "Vox Terminal.app"
DEFAULT_ANALYSIS = ROOT / "build" / "VoxTerminal" / "PYZ-00.toc"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    document = build_sbom(args.app, args.analysis)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"Wrote SPDX SBOM: {args.output}")
    return 0


def build_sbom(app: Path, analysis: Path) -> dict[str, object]:
    if not app.is_dir():
        raise FileNotFoundError(f"App bundle not found: {app}")
    if not analysis.is_file():
        raise FileNotFoundError(f"PyInstaller analysis not found: {analysis}")

    distribution_names = _analyzed_distributions(analysis)
    distribution_names.update(_bundled_module_distributions(app))
    distribution_names.update(_bundled_metadata_names(app))
    distribution_names.add("vox-terminal")

    packages = [_package_record(name) for name in sorted(distribution_names, key=str.casefold)]
    package_ids = {str(package["name"]): str(package["SPDXID"]) for package in packages}
    project_id = package_ids["vox-terminal"]
    fingerprint = hashlib.sha256(
        "\n".join(
            f"{package['name']}=={package['versionInfo']}" for package in packages
        ).encode()
    ).hexdigest()[:16]
    project_version = next(
        str(package["versionInfo"])
        for package in packages
        if package["name"] == "vox-terminal"
    )
    namespace = (
        "https://github.com/jaswanth1524/vox-terminal/"
        f"spdx/{project_version}/{fingerprint}"
    )
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": project_id,
        }
    ]
    relationships.extend(
        {
            "spdxElementId": project_id,
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": str(package["SPDXID"]),
        }
        for package in packages
        if package["name"] != "vox-terminal"
    )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"Vox-Terminal-{project_version}-macOS-arm64",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "creators": ["Tool: Vox Terminal SPDX generator"],
        },
        "documentDescribes": [project_id],
        "packages": packages,
        "relationships": relationships,
    }


def _analyzed_distributions(analysis: Path) -> set[str]:
    pyz_toc = ast.literal_eval(analysis.read_text())
    module_names = {entry[0].partition(".")[0] for entry in pyz_toc[1]}
    package_map = metadata.packages_distributions()
    return {
        distribution
        for module_name in module_names
        for distribution in package_map.get(module_name, ())
    }


def _bundled_metadata_names(app: Path) -> set[str]:
    names: set[str] = set()
    for root in (
        app / "Contents" / "Frameworks",
        app / "Contents" / "Resources",
    ):
        for metadata_dir in root.glob("*.dist-info"):
            metadata_file = metadata_dir / "METADATA"
            if not metadata_file.is_file():
                continue
            for line in metadata_file.read_text(errors="replace").splitlines():
                if line.startswith("Name: "):
                    names.add(line.removeprefix("Name: ").strip())
                    break
    return names


def _bundled_module_distributions(app: Path) -> set[str]:
    package_map = metadata.packages_distributions()
    module_names: set[str] = set()
    for root in (
        app / "Contents" / "Frameworks",
        app / "Contents" / "Resources",
    ):
        for item in root.iterdir():
            if item.name.endswith(".dist-info"):
                continue
            module_names.add(item.name.partition(".")[0])
    return {
        distribution
        for module_name in module_names
        for distribution in package_map.get(module_name, ())
    }


def _package_record(name: str) -> dict[str, object]:
    distribution = metadata.distribution(name)
    canonical_name = re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower()
    version = distribution.version
    package_id = "SPDXRef-Package-" + re.sub(
        r"[^A-Za-z0-9.-]",
        "-",
        f"{canonical_name}-{version}",
    )
    return {
        "name": canonical_name,
        "SPDXID": package_id,
        "versionInfo": version,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": "NOASSERTION",
        "copyrightText": "NOASSERTION",
        "primaryPackagePurpose": (
            "APPLICATION" if canonical_name == "vox-terminal" else "LIBRARY"
        ),
        "externalRefs": [
            {
                "referenceCategory": "PACKAGE-MANAGER",
                "referenceType": "purl",
                "referenceLocator": f"pkg:pypi/{quote(canonical_name)}@{quote(version)}",
            }
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
