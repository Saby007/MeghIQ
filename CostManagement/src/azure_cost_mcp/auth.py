"""Authentication module using Azure Identity (DefaultAzureCredential).

Picks up credentials from:
  1. az login (Azure CLI)
  2. Environment variables (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET)
  3. Managed Identity (when running in Azure)
"""

from __future__ import annotations

import logging
import os

from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

_credential: DefaultAzureCredential | None = None


def get_credential() -> DefaultAzureCredential:
    """Return a cached DefaultAzureCredential instance."""
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
        logger.info("Azure credential initialised (DefaultAzureCredential)")
    return _credential


def get_subscription_id() -> str:
    """Return the Azure subscription ID from environment or raise."""
    sub_id = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
    if not sub_id:
        raise ValueError(
            "AZURE_SUBSCRIPTION_ID environment variable is required. "
            "Set it to your target Azure subscription ID."
        )
    return sub_id


def get_token(scope: str = "https://management.azure.com/.default") -> str:
    """Acquire a bearer token for the Azure Management plane."""
    credential = get_credential()
    token = credential.get_token(scope)
    return token.token
