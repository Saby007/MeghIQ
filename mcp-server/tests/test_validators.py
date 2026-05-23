"""Unit tests for ``tools/validators.py``.

These tests are fully hermetic — no Azure, no network. They lock down the
security-critical input layer so future refactors cannot silently weaken a
regex or allow path traversal.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Make the project root importable when pytest is run from any cwd.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.validators import (  # noqa: E402
    sanitize_error_message,
    sanitize_kql_input,
    validate_azure_resource_id,
    validate_budget_name,
    validate_management_group_id,
    validate_output_directory,
    validate_output_path,
    validate_resource_group,
    validate_subscription_id,
)


# ── validate_subscription_id ────────────────────────────────────────────

VALID_UUID = "12345678-1234-1234-1234-1234567890ab"


def test_validate_subscription_id_accepts_canonical_uuid():
    assert validate_subscription_id(VALID_UUID) == VALID_UUID


def test_validate_subscription_id_accepts_uppercase_hex():
    upper = VALID_UUID.upper()
    assert validate_subscription_id(upper) == upper


def test_validate_subscription_id_strips_whitespace():
    assert validate_subscription_id(f"  {VALID_UUID}  ") == VALID_UUID


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "not-a-uuid",
        "12345678-1234-1234-1234-1234567890",       # too short
        "12345678-1234-1234-1234-1234567890abcd",   # too long
        "12345678_1234_1234_1234_1234567890ab",     # wrong separators
        "12345678-1234-1234-1234-1234567890ag",     # non-hex
        "'; DROP TABLE users; --",
        "../etc/passwd",
    ],
)
def test_validate_subscription_id_rejects_invalid(bad: str):
    with pytest.raises(ValueError, match="Invalid subscription ID"):
        validate_subscription_id(bad)


# ── validate_resource_group ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    [
        "rg-prod",
        "rg_dev_01",
        "RG.With.Dots",
        "a",                  # min length 1
        "a" * 90,             # max length 90
    ],
)
def test_validate_resource_group_accepts_valid(name: str):
    assert validate_resource_group(name) == name


@pytest.mark.parametrize(
    "bad",
    [
        "",
        " ",                  # empty after strip
        "rg with space",
        "rg/with/slash",
        "rg;DROP",
        "rg$injection",
        "a" * 91,             # one over the limit
        "rg\nnewline",
    ],
)
def test_validate_resource_group_rejects_invalid(bad: str):
    with pytest.raises(ValueError, match="Invalid resource group name"):
        validate_resource_group(bad)


# ── validate_budget_name / validate_management_group_id ─────────────────


def test_validate_budget_name_accepts_valid():
    assert validate_budget_name("monthly-budget_2026") == "monthly-budget_2026"


def test_validate_budget_name_rejects_special_chars():
    with pytest.raises(ValueError, match="Invalid budget name"):
        validate_budget_name("budget with space")


def test_validate_management_group_id_accepts_valid():
    assert validate_management_group_id("mg-platform") == "mg-platform"


def test_validate_management_group_id_rejects_invalid():
    with pytest.raises(ValueError, match="Invalid management group"):
        validate_management_group_id("mg/with/slash")


# ── sanitize_kql_input ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "virtual machine",
        "Microsoft.Compute",
        "rg_prod-01",
        "search 1.2.3",
    ],
)
def test_sanitize_kql_input_accepts_safe(value: str):
    assert sanitize_kql_input(value) == value


def test_sanitize_kql_input_rejects_empty():
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_kql_input("")


def test_sanitize_kql_input_rejects_whitespace_only():
    with pytest.raises(ValueError, match="cannot be empty"):
        sanitize_kql_input("   ")


@pytest.mark.parametrize(
    "bad",
    [
        "name'; drop table",
        "rg | project *",
        "value\"quoted",
        "name\\path",
        "name`backtick",
        "name<script>",
        "name\nnewline",
    ],
)
def test_sanitize_kql_input_rejects_kql_metachars(bad: str):
    with pytest.raises(ValueError, match="Invalid characters"):
        sanitize_kql_input(bad)


# ── validate_azure_resource_id ──────────────────────────────────────────


def test_validate_azure_resource_id_accepts_subscriptions_prefix():
    rid = f"subscriptions/{VALID_UUID}/resourceGroups/rg-prod"
    assert validate_azure_resource_id(rid) == rid


def test_validate_azure_resource_id_accepts_providers_prefix():
    rid = "providers/Microsoft.Management/managementGroups/mg-platform"
    assert validate_azure_resource_id(rid) == rid


def test_validate_azure_resource_id_strips_leading_slash():
    rid = f"/subscriptions/{VALID_UUID}"
    assert validate_azure_resource_id(rid) == rid.lstrip("/")


def test_validate_azure_resource_id_rejects_empty():
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_azure_resource_id("")


def test_validate_azure_resource_id_rejects_other_prefix():
    with pytest.raises(ValueError, match="must start with"):
        validate_azure_resource_id("tenants/foo")


@pytest.mark.parametrize(
    "bad",
    [
        "subscriptions/../etc/passwd",
        "subscriptions//double-slash",
        f"subscriptions/{VALID_UUID}/..",
    ],
)
def test_validate_azure_resource_id_rejects_path_traversal(bad: str):
    with pytest.raises(ValueError, match="unsafe path segments"):
        validate_azure_resource_id(bad)


@pytest.mark.parametrize(
    "bad",
    [
        "subscriptions/abc def",          # space
        "subscriptions/abc;rm -rf",       # shell metachar
        "subscriptions/abc?query=1",      # query string
        "subscriptions/abc#fragment",     # fragment
    ],
)
def test_validate_azure_resource_id_rejects_disallowed_chars(bad: str):
    with pytest.raises(ValueError, match="disallowed characters"):
        validate_azure_resource_id(bad)


# ── validate_output_path ────────────────────────────────────────────────


def test_validate_output_path_accepts_path_under_tmp(tmp_path: Path):
    target = tmp_path / "report.pdf"
    result = validate_output_path(str(target), [".pdf"])
    assert Path(result) == target.resolve()


def test_validate_output_path_accepts_path_under_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "out" / "report.csv"
    result = validate_output_path(str(target), [".csv", ".pdf"])
    assert Path(result) == target.resolve()


def test_validate_output_path_rejects_bad_extension(tmp_path: Path):
    target = tmp_path / "evil.exe"
    with pytest.raises(ValueError, match="Invalid file extension"):
        validate_output_path(str(target), [".pdf"])


def test_validate_output_path_rejects_outside_safe_roots(tmp_path: Path, monkeypatch):
    # Force cwd to one tmp dir; ask to write to a sibling outside both
    # the cwd tree and the system temp root.
    monkeypatch.chdir(tmp_path)
    # Use a path that's guaranteed to be outside cwd and tmp on Windows.
    if os.name == "nt":
        outside = "C:\\Windows\\System32\\evil.pdf"
    else:
        outside = "/root/evil.pdf"
    # Skip if the resolved path happens to land under the real temp (CI quirk).
    resolved_outside = Path(outside).resolve()
    real_tmp = Path(tempfile.gettempdir()).resolve()
    if str(resolved_outside).startswith(str(real_tmp)):
        pytest.skip("test path unexpectedly resolved under tempdir")
    with pytest.raises(ValueError, match="under the working directory or temp"):
        validate_output_path(outside, [".pdf"])


def test_validate_output_path_normalises_traversal_under_tmp(tmp_path: Path):
    # ``..`` that still resolves under tmp is allowed because the final
    # resolved path is what the validator checks, not the raw input.
    target = tmp_path / "sub" / ".." / "report.pdf"
    result = validate_output_path(str(target), [".pdf"])
    assert Path(result) == (tmp_path / "report.pdf").resolve()


# ── validate_output_directory ───────────────────────────────────────────


def test_validate_output_directory_accepts_tmp(tmp_path: Path):
    result = validate_output_directory(str(tmp_path))
    assert Path(result) == tmp_path.resolve()


def test_validate_output_directory_rejects_outside_safe_roots(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    if os.name == "nt":
        outside = "C:\\Windows\\System32"
    else:
        outside = "/root"
    resolved_outside = Path(outside).resolve()
    real_tmp = Path(tempfile.gettempdir()).resolve()
    if str(resolved_outside).startswith(str(real_tmp)):
        pytest.skip("test path unexpectedly resolved under tempdir")
    with pytest.raises(ValueError, match="under the working directory or temp"):
        validate_output_directory(outside)


# ── sanitize_error_message ──────────────────────────────────────────────


def test_sanitize_error_message_passes_short_messages_through():
    msg = "Short error"
    assert sanitize_error_message(msg) == msg


def test_sanitize_error_message_truncates_long_messages():
    msg = "x" * 500
    out = sanitize_error_message(msg, max_length=200)
    assert out.endswith("...")
    assert len(out) == 203  # 200 chars + 3-char ellipsis


def test_sanitize_error_message_honours_custom_max_length():
    out = sanitize_error_message("hello world", max_length=5)
    assert out == "hello..."
