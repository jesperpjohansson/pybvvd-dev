"""
Patch the OpenAPI (swagger.json) schema to relax required fields.

The organisations in the API's test environment are not compatible with the
official schema. This script removes selected fields from "required" so that
test data can pass validation.
"""

import argparse
import json
from pathlib import Path
from typing import Any


def read_swagger(path: Path) -> dict[str, Any]:
    """Read and validate the top-level Swagger JSON object."""
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)

    if not isinstance(data, dict):
        exc_msg = f"{path} did not contain a JSON object"
        raise TypeError(exc_msg)

    return data


def get_typed_schema(swagger: dict[str, Any], schema_key: str) -> dict[str, Any]:
    """Return a schema object from components.schemas by key."""
    components = swagger.get("components")
    schemas = components.get("schemas") if isinstance(components, dict) else None

    if not isinstance(schemas, dict):
        exc_msg = "components.schemas is missing or not an object"
        raise TypeError(exc_msg)

    schema = schemas.get(schema_key)
    if not isinstance(schema, dict):
        exc_msg = f"Schema {schema_key!r} is missing or not an object"
        raise TypeError(exc_msg)

    return schema


def get_typed_required(swagger: dict[str, Any], schema_key: str) -> list[str]:
    """Return the validated required-field list for a schema."""
    schema = get_typed_schema(swagger, schema_key)
    required = schema.get("required")

    if not isinstance(required, list):
        exc_msg = f"Schema {schema_key!r}.required is missing or not a list"
        raise TypeError(exc_msg)

    if not all(isinstance(item, str) for item in required):
        exc_msg = f"Schema {schema_key!r}.required must contain only strings"
        raise TypeError(exc_msg)

    return required


def write_swagger(swagger: dict[str, Any], path: Path) -> None:
    """Write the patched Swagger JSON object to disk."""
    with path.open("w", encoding="utf-8") as stream:
        json.dump(swagger, stream, ensure_ascii=False, indent=1)
        stream.write("\n")


def remove_required_fields(
    swagger: dict[str, Any], schema_key: str, *fields: str
) -> None:
    """Remove selected field names from a schema's required list."""
    required = get_typed_required(swagger, schema_key)
    for field in fields:
        if field in required:
            required.remove(field)


def main() -> None:
    """Patch selected required fields in the input Swagger schema."""
    parser = argparse.ArgumentParser(description="Patch swagger schema required fields")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to input swagger.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output patched swagger.json",
    )

    args = parser.parse_args()

    swagger = read_swagger(args.input)

    remove_required_fields(swagger, "JuridiskForm", "kod", "klartext")
    remove_required_fields(swagger, "VerksamOrganisation", "kod")

    write_swagger(swagger, args.output)


if __name__ == "__main__":
    main()
