"""Input validation and sanitization helpers for MeghIQ MCP Server.

Provides validation for Azure resource identifiers, KQL query inputs,
and file system paths to prevent injection and path traversal attacks.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

# Azure subscription ID / GUID format
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Azure resource name: alphanumeric, dot, underscore, hyphen (1-90 chars)
_RESOURCE_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,90}$")

# Safe characters for KQL string interpolation
_SAFE_KQL_RE = re.compile(r"^[a-zA-Z0-9 _.\-]+$")


def validate_subscription_id(sub_id: str) -> str:
    """Validate that a string is a well-formed Azure subscription UUID."""
    sub_id = sub_id.strip()
    if not _UUID_RE.match(sub_id):
        raise ValueError("Invalid subscription ID format: must be a valid UUID")
    return sub_id


def validate_resource_group(name: str) -> str:
    """Validate an Azure resource group name."""
    name = name.strip()
    if not _RESOURCE_NAME_RE.match(name):
        raise ValueError(
            "Invalid resource group name: only alphanumeric, '.', '_', '-' "
            "allowed (max 90 chars)"
        )
    return name


def validate_budget_name(name: str) -> str:
    """Validate an Azure budget name."""
    name = name.strip()
    if not _RESOURCE_NAME_RE.match(name):
        raise ValueError(
            "Invalid budget name: only alphanumeric, '.', '_', '-' "
            "allowed (max 90 chars)"
        )
    return name


def validate_management_group_id(mg_id: str) -> str:
    """Validate an Azure management group identifier."""
    mg_id = mg_id.strip()
    if not re.match(r"^[a-zA-Z0-9._-]{1,90}$", mg_id):
        raise ValueError("Invalid management group ID format")
    return mg_id


def sanitize_kql_input(value: str) -> str:
    """Sanitize a value for safe interpolation into KQL queries.

    Only allows alphanumeric characters, spaces, dots, underscores, and hyphens.
    """
    value = value.strip()
    if not value:
        raise ValueError("Search term cannot be empty")
    if not _SAFE_KQL_RE.match(value):
        raise ValueError(
            "Invalid characters in search term: only alphanumeric, "
            "spaces, '.', '_', '-' allowed"
        )
    return value


def validate_azure_resource_id(resource_id: str) -> str:
    """Validate an Azure resource ID to prevent SSRF and path traversal.

    Must start with 'subscriptions/' or 'providers/' and contain only
    safe path characters.
    """
    resource_id = resource_id.strip().lstrip("/")
    if not resource_id:
        raise ValueError("Resource ID cannot be empty")
    if not re.match(r"^(subscriptions|providers)/", resource_id):
        raise ValueError(
            "Invalid Azure resource ID: must start with "
            "'subscriptions/' or 'providers/'"
        )
    if ".." in resource_id or "//" in resource_id:
        raise ValueError(
            "Invalid Azure resource ID: contains unsafe path segments"
        )
    if not re.match(r"^[a-zA-Z0-9/_.\-]+$", resource_id):
        raise ValueError(
            "Invalid Azure resource ID: contains disallowed characters"
        )
    return resource_id


def validate_output_path(path: str, allowed_extensions: list[str]) -> str:
    """Validate a file output path to prevent path traversal.

    Ensures the path has an allowed extension and resolves to a location
    under the current working directory or system temp directory.
    """
    resolved = Path(path).resolve()
    ext = resolved.suffix.lower()
    if ext not in allowed_extensions:
        raise ValueError(
            f"Invalid file extension '{ext}': allowed {allowed_extensions}"
        )
    cwd = Path.cwd().resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    if not (str(resolved).startswith(str(cwd)) or str(resolved).startswith(str(tmp))):
        raise ValueError(
            "Output path must be under the working directory or temp directory"
        )
    return str(resolved)


def validate_output_directory(dir_path: str) -> str:
    """Validate an output directory path to prevent path traversal.

    Ensures the directory resolves to a location under the current working
    directory or system temp directory.
    """
    resolved = Path(dir_path).resolve()
    cwd = Path.cwd().resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    if not (str(resolved).startswith(str(cwd)) or str(resolved).startswith(str(tmp))):
        raise ValueError(
            "Output directory must be under the working directory or temp directory"
        )
    return str(resolved)


def sanitize_error_message(message: str, max_length: int = 200) -> str:
    """Truncate an error message to prevent leaking sensitive internal details."""
    if len(message) > max_length:
        return message[:max_length] + "..."
    return message
