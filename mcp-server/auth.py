"""Azure authentication helpers for MeghIQ MCP Server.

Picks up credentials from:
  1. az login (Azure CLI)
  2. Environment variables (AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET)
  3. Managed Identity (when running in Azure)
"""

from __future__ import annotations

import logging
import os

from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resourcegraph import ResourceGraphClient

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
    """Get Azure subscription ID from environment."""
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


def get_cost_management_client() -> CostManagementClient:
    return CostManagementClient(credential=get_credential())


def get_resource_graph_client() -> ResourceGraphClient:
    return ResourceGraphClient(credential=get_credential())


def get_monitor_client(subscription_id: str | None = None) -> MonitorManagementClient:
    return MonitorManagementClient(
        credential=get_credential(),
        subscription_id=subscription_id or get_subscription_id(),
    )


def get_resource_client(subscription_id: str | None = None) -> ResourceManagementClient:
    return ResourceManagementClient(
        credential=get_credential(),
        subscription_id=subscription_id or get_subscription_id(),
    )
