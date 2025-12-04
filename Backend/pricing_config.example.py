"""
Azure Pricing Configuration Examples

This file shows how to customize the Azure pricing calculation behavior.
Copy this to your code and modify AZURE_PRICING_CONFIG as needed.
"""

# Default Configuration (what the system uses by default)
DEFAULT_CONFIG = {
    # Standard month calculation (365 days / 12 months * 24 hours)
    "hours_per_month": 730,
    
    # Timeout for Azure Retail Prices API calls (in seconds)
    "api_timeout_seconds": 10,
    
    # Azure Retail Prices API endpoint (public, no auth required)
    "api_base_url": "https://prices.azure.com/api/retail/prices",
    
    # Maximum number of results to fetch per API query
    "max_results_per_query": 20,
    
    # Unit conversion rules - how to convert various units to monthly costs
    # Each unit has a multiplier and a flag indicating if it's time-based
    "unit_conversions": {
        "Hour": {"multiplier": 730, "to_monthly": True},
        "1 Hour": {"multiplier": 730, "to_monthly": True},
        "Day": {"multiplier": 30, "to_monthly": True},
        "Month": {"multiplier": 1, "to_monthly": False},
        "GB": {"multiplier": 1, "to_monthly": False},  # Usage-based, not time
        "10K": {"multiplier": 1, "to_monthly": False},  # Transaction-based
        "1000 Hours": {"multiplier": 0.73, "to_monthly": True},
    },
    
    # Data transfer costs (per GB)
    "data_transfer_costs": {
        "inter_region_per_gb": 0.02,      # Between Azure regions
        "egress_internet_per_gb": 0.087,  # Outbound to internet (first 10TB)
        "intra_region_per_gb": 0.0        # Within same region (usually free)
    }
}


# Example: Development/Testing Configuration (faster timeout, fewer results)
DEV_CONFIG = {
    "hours_per_month": 730,
    "api_timeout_seconds": 5,  # Faster timeout for dev
    "api_base_url": "https://prices.azure.com/api/retail/prices",
    "max_results_per_query": 10,  # Fewer results for speed
    "unit_conversions": {
        "Hour": {"multiplier": 730, "to_monthly": True},
        "1 Hour": {"multiplier": 730, "to_monthly": True},
        "Month": {"multiplier": 1, "to_monthly": False},
    },
    "data_transfer_costs": {
        "inter_region_per_gb": 0.02,
        "egress_internet_per_gb": 0.087,
        "intra_region_per_gb": 0.0
    }
}


# Example: Production Configuration (longer timeout, comprehensive results)
PROD_CONFIG = {
    "hours_per_month": 730,
    "api_timeout_seconds": 30,  # Allow more time for complex queries
    "api_base_url": "https://prices.azure.com/api/retail/prices",
    "max_results_per_query": 50,  # Get all available SKU options
    "unit_conversions": {
        "Hour": {"multiplier": 730, "to_monthly": True},
        "1 Hour": {"multiplier": 730, "to_monthly": True},
        "Day": {"multiplier": 30, "to_monthly": True},
        "Week": {"multiplier": 4.33, "to_monthly": True},  # ~4.33 weeks per month
        "Month": {"multiplier": 1, "to_monthly": False},
        "GB": {"multiplier": 1, "to_monthly": False},
        "TB": {"multiplier": 1024, "to_monthly": False},  # Convert TB to GB
        "10K": {"multiplier": 1, "to_monthly": False},
        "100K": {"multiplier": 1, "to_monthly": False},
        "1M": {"multiplier": 1, "to_monthly": False},
        "1000 Hours": {"multiplier": 0.73, "to_monthly": True},
    },
    "data_transfer_costs": {
        "inter_region_per_gb": 0.02,
        "egress_internet_per_gb": 0.087,
        "intra_region_per_gb": 0.0
    }
}


# Example: Custom Month Definition (business month = 22 working days * 8 hours)
BUSINESS_HOURS_CONFIG = {
    "hours_per_month": 176,  # 22 days * 8 hours
    "api_timeout_seconds": 10,
    "api_base_url": "https://prices.azure.com/api/retail/prices",
    "max_results_per_query": 20,
    "unit_conversions": {
        "Hour": {"multiplier": 176, "to_monthly": True},  # Business hours only
        "1 Hour": {"multiplier": 176, "to_monthly": True},
        "Day": {"multiplier": 22, "to_monthly": True},  # Working days
        "Month": {"multiplier": 1, "to_monthly": False},
    },
    "data_transfer_costs": {
        "inter_region_per_gb": 0.02,
        "egress_internet_per_gb": 0.087,
        "intra_region_per_gb": 0.0
    }
}


# Example: High Data Transfer Configuration (different egress costs)
HIGH_BANDWIDTH_CONFIG = {
    "hours_per_month": 730,
    "api_timeout_seconds": 10,
    "api_base_url": "https://prices.azure.com/api/retail/prices",
    "max_results_per_query": 20,
    "unit_conversions": {
        "Hour": {"multiplier": 730, "to_monthly": True},
        "1 Hour": {"multiplier": 730, "to_monthly": True},
        "Month": {"multiplier": 1, "to_monthly": False},
    },
    "data_transfer_costs": {
        "inter_region_per_gb": 0.02,
        "egress_internet_per_gb": 0.05,  # 50TB+ tier pricing
        "intra_region_per_gb": 0.0
    }
}


# How to use custom config:
"""
# In your code:
from orchestrator import get_azure_pricing, estimate_architecture_cost

# Use custom config for pricing API calls
pricing = await get_azure_pricing("app service", "eastus", config=PROD_CONFIG)

# Use custom config for cost estimation
result = await estimate_architecture_cost(xml_content, config=BUSINESS_HOURS_CONFIG)
"""


# Adding new unit conversions:
"""
To add support for new units (e.g., "per 100K requests"):

1. Add to unit_conversions dictionary:
   "100K": {"multiplier": 1, "to_monthly": False}

2. The calculate_monthly_cost() function will automatically use it:
   - Exact match: unit == "100K"
   - Partial match: "100k" in unit.lower() or "100000" in unit.lower()

3. If the unit is not found, it logs a warning and assumes monthly pricing
"""


# Best Practices:
"""
1. **hours_per_month**: 
   - 730 = standard (365/12*24)
   - 720 = even (30*24)
   - 744 = 31-day month
   - 176 = business hours (22 days * 8 hours)

2. **api_timeout_seconds**:
   - 5 seconds = fast, may fail on slow connections
   - 10 seconds = balanced (default)
   - 30 seconds = patient, for comprehensive queries

3. **max_results_per_query**:
   - 10 = fast, may miss some SKUs
   - 20 = balanced (default)
   - 50+ = comprehensive, all SKU options

4. **unit_conversions**:
   - Always include common units: Hour, Day, Month
   - Add specialized units for your services
   - Multiplier should convert to monthly cost

5. **data_transfer_costs**:
   - Update based on your Azure pricing tier
   - Different tiers have different egress costs:
     * First 10TB: $0.087/GB
     * 10-50TB: $0.083/GB
     * 50-150TB: $0.07/GB
     * 150TB+: $0.05/GB
"""
