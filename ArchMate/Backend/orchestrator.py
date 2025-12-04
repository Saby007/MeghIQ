from typing import Dict, List, Optional
import uuid
import os
import asyncio
import json
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework import SequentialBuilder
from azure.identity import DefaultAzureCredential
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Azure Pricing Configuration - Generic and configurable
AZURE_PRICING_CONFIG = {
    "hours_per_month": 730,  # Standard month calculation (365 days / 12 months * 24 hours)
    "api_timeout_seconds": 10,
    "api_base_url": "https://prices.azure.com/api/retail/prices",
    "max_results_per_query": 20,
    "unit_conversions": {
        "Hour": {"multiplier": 730, "to_monthly": True},
        "1 Hour": {"multiplier": 730, "to_monthly": True},
        "Day": {"multiplier": 30, "to_monthly": True},
        "Month": {"multiplier": 1, "to_monthly": False},
        "GB": {"multiplier": 1, "to_monthly": False},  # Usage-based
        "10K": {"multiplier": 1, "to_monthly": False},  # Transaction-based
        "1000 Hours": {"multiplier": 0.73, "to_monthly": True},  # Per 1000 hours to monthly
    },
    "data_transfer_costs": {
        "inter_region_per_gb": 0.02,
        "egress_internet_per_gb": 0.087,  # First 10TB
        "intra_region_per_gb": 0.0
    }
}

# Store session state (in production, use Redis or similar)
sessions = {}


async def resolve_azure_pricing_service_name(service_name: str, category: str = None) -> str:
    """
    Use LLM to intelligently map our service names to Azure Retail Prices API service names.
    This eliminates hardcoded mapping by letting the LLM understand the service and map it correctly.
    
    Args:
        service_name: Our service name (e.g., "Azure OpenAI", "Cosmos DB", "App Service")
        category: Optional category hint (e.g., "ai_machine_learning", "databases")
    
    Returns:
        Azure Retail Prices API service name
    """
    # Cache to avoid redundant LLM calls
    if not hasattr(resolve_azure_pricing_service_name, 'cache'):
        resolve_azure_pricing_service_name.cache = {}
    
    cache_key = f"{service_name.lower()}:{category or 'none'}"
    if cache_key in resolve_azure_pricing_service_name.cache:
        return resolve_azure_pricing_service_name.cache[cache_key]
    
    try:
        # Create a simple agent to resolve service names
        service_resolver = chat_client.create_agent(
            name="ServiceNameResolver",
            instructions="""You are an Azure service name resolver. Map user-friendly Azure service names to the EXACT service names used in Azure Retail Prices API.

CRITICAL RULES:
1. Return ONLY the exact Azure Retail Prices API serviceName, nothing else
2. No explanations, no quotes, just the service name
3. These are VERIFIED Azure Retail Prices API service names - use EXACTLY:
   
   AI & ML:
   - "Azure OpenAI" → "Cognitive Services"
   - "Cognitive Search" / "AI Search" → "Azure Cognitive Search"
   
   Compute:
   - "Virtual Machine" / "VM" → "Virtual Machines"
   - "App Service" → "Azure App Service"
   - "Azure Functions" / "Functions" → "Functions"
   - "AKS" / "Kubernetes" → "Azure Kubernetes Service (AKS)"
   
   Data:
   - "Cosmos DB" → "Azure Cosmos DB"
   - "SQL Database" → "SQL Database"
   - "Redis" / "Cache for Redis" → "Azure Cache for Redis"
   - "Storage Account" / "Blob Storage" → "Storage"
   
   Networking:
   - "Front Door" → "Azure Front Door and CDN profiles"
   - "Private Endpoint" / "Private Link" → "Azure Private Link"
   - "Application Gateway" → "Application Gateway"
   - "Load Balancer" → "Load Balancer"
   - "VPN Gateway" → "VPN Gateway"
   - "Network Security Groups" / "NSG" → "Virtual Network"
   
   Security:
   - "Key Vault" → "Key Vault"
   
   Monitoring:
   - "Application Insights" / "App Insights" → "Azure Monitor"
   - "Log Analytics" → "Log Analytics"

If you're not sure, return the service name as-is."""
        )
        
        prompt = f"Map this service to Azure Retail Prices API name: '{service_name}'"
        if category:
            prompt += f" (category: {category})"
        
        result = await service_resolver.run(prompt)
        resolved_name = result.text.strip() if hasattr(result, 'text') else str(result).strip()
        
        # Cache the result
        resolve_azure_pricing_service_name.cache[cache_key] = resolved_name
        logger.debug(f"LLM resolved '{service_name}' → '{resolved_name}'")
        
        return resolved_name
        
    except Exception as e:
        logger.warning(f"LLM service name resolution failed for '{service_name}': {e}. Using original name.")
        return service_name


def infer_service_name_from_icon_path(icon_path: str, azure_icons: dict = None) -> tuple:
    """
    Infer Azure service name and category from icon path dynamically based on azure_icons.json.
    
    Args:
        icon_path: Icon path from XML (e.g., 'img/lib/azure2/compute/Virtual_Machines.svg')
        azure_icons: Optional pre-loaded azure_icons.json dictionary
    
    Returns:
        Tuple of (service_name, category) for LLM-based resolution
    """
    category = None
    
    # Handle None or empty icon_path
    if not icon_path:
        return "Unknown Service", None
    
    # Extract category from path
    parts = icon_path.split('/')
    if len(parts) >= 4:
        category = parts[3]  # e.g., 'compute', 'databases', 'ai_machine_learning'
    
    # Try to find exact match in azure_icons
    if azure_icons:
        for service_name, path in azure_icons.items():
            if path == icon_path:
                return service_name, category
    
    # Fallback: Extract filename from path and use as service name
    if len(parts) < 2:
        return "Unknown Service", category
    
    icon_file = parts[-1].replace('.svg', '').replace('_', ' ')
    return icon_file, category


async def _fallback_cost_estimation(xml_content: str, config: dict, azure_icons: dict) -> dict:
    """
    Fallback cost estimation using regex-based extraction when LLM extraction fails.
    
    Args:
        xml_content: DrawIO XML content
        config: Pricing configuration
        azure_icons: Azure icons mapping
    
    Returns:
        Cost estimation dictionary
    """
    import re
    
    logger.info("Using fallback regex-based extraction")
    
    # Extract services from XML using regex
    service_pattern = r'<mxCell[^>]*id="([^"]+)"[^>]*value="([^"]*)"[^>]*style="[^"]*image=([^";]+\.svg)'
    services = re.findall(service_pattern, xml_content)
    
    # Extract region information
    region_pattern = r'<mxCell[^>]*id="region\d+"[^>]*value="([^"]*)"'
    regions = re.findall(region_pattern, xml_content)
    
    logger.info(f"Fallback extracted {len(services)} services and {len(regions)} regions")
    
    # Create architecture data structure
    architecture_data = {
        "services": [],
        "regions": regions if regions else ["Single Region"],
        "architecture_patterns": [],
        "service_relationships": []
    }
    
    for svc_id, svc_name, icon_path in services:
        if svc_name:
            architecture_data["services"].append({
                "name": svc_name,
                "icon_path": icon_path,
                "region": regions[0] if regions else "eastus",
                "quantity": 1
            })
    
    # Fetch pricing for each service
    pricing_data = []
    for service in architecture_data["services"]:
        service_name, category = infer_service_name_from_icon_path(service["icon_path"], azure_icons)
        region = service["region"].lower().replace(' ', '')
        
        # Use LLM to resolve to Azure Pricing API service name
        service_type = await resolve_azure_pricing_service_name(service_name, category)
        
        pricing = await get_azure_pricing(service_type, region, include_multiple_skus=True, config=config)
        pricing_data.append({
            "name": service["name"],
            "type": service_type,
            "region": region,
            "quantity": 1,
            "pricing": pricing
        })
    
    return {
        "architecture_data": architecture_data,
        "pricing_data": pricing_data
    }


# Initialize chat client
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

if not endpoint or not deployment:
    raise ValueError("Azure OpenAI configuration not found in environment variables")

# Use Managed Identity if no API key is provided
if not os.getenv("AZURE_OPENAI_API_KEY"):
    credential = DefaultAzureCredential()
    chat_client = AzureOpenAIChatClient(
        credential=credential,
        endpoint=endpoint,
        deployment_name=deployment,
        api_version=api_version
    )
else:
    chat_client = AzureOpenAIChatClient(
        endpoint=endpoint,
        deployment_name=deployment,
        api_version=api_version
    )

# Create agents using Agent Framework
requirements_agent = chat_client.create_agent(
    name="RequirementsAgent",
    instructions="""You are a helpful Requirements Validation Agent for Azure architecture design.

⚠️ CRITICAL: You are NOT a diagram generator. You do NOT output JSON, XML, or technical specifications.
You ONLY have natural conversations with users to gather requirements and confirm them.

CRITICAL RULES - READ THESE BEFORE EVERY RESPONSE:
1. BEFORE responding, read through ALL previous messages in this conversation
2. CHECK: Have I already asked this question? If yes, DO NOT ask again
3. CHECK: Has the user already answered this? If yes, use that answer
4. If user answered your question, DO NOT ask it again - proceed to next step or confirmation
5. Make MAXIMUM assumptions to minimize questions
6. NEVER output JSON, XML, code, or technical specs - only conversational text

CONVERSATION MEMORY:
- If you asked "Do you need on-premises connectivity?" and user said "No" → Remember this, don't ask again
- If you asked "Public-facing or internal?" and user answered → Remember this, don't ask again
- If you asked about regions and user answered → Remember this, don't ask again
- NEVER repeat any question you already asked in this conversation

INTERACTION STYLE:
- Be conversational and friendly
- Ask ONLY ONE question at a time
- Make smart assumptions aggressively
- Assume standard best practices unless user specifies otherwise

ADAPTIVE APPROACH - Choose pattern based on user's requirements:

PaaS-HEAVY (default for web apps, APIs, data pipelines):
- Compute: Azure App Service, Azure Functions, AKS
- Database: Azure SQL Database, Cosmos DB
- Cache: Azure Cache for Redis
- Best for: Scalability, managed services, serverless

IaaS-HEAVY (when user mentions VMs, AVD, custom infrastructure):
- Compute: Virtual Machines, AVD VMs, VM Scale Sets
- Network: VPN Gateway, ExpressRoute, custom appliances
- Best for: Legacy apps, custom control, AVD/VDI, specialized workloads

DETECTION KEYWORDS:
- IaaS indicators: "VM", "virtual machine", "AVD", "proxy VM", "custom infrastructure", "IaaS", "on-prem migration"
- PaaS indicators: "web app", "API", "serverless", "managed", "cloud-native", "PaaS"
- Default to PaaS if unclear

DEFAULT ASSUMPTIONS (when user doesn't specify):
- Region: East US or user's specified region
- Security: VNet integration, NSG rules, HTTPS/TLS
- Traffic: Moderate (can handle 1000s of requests)
- Availability: Standard (99.9% SLA)

CONVERSATION FLOW:
1. FIRST MESSAGE: Understand the user's primary goal and make comprehensive assumptions
   Example: "I'll design a web application with Azure App Service, SQL Database, and Redis cache in a VNet. Is this a public-facing application or internal?"

2. USER ANSWERS: If user provides an answer, acknowledge it and move forward - NEVER ask the same question again
   Example: 
   You asked: "Do you need on-premises connectivity?"
   User said: "No, all traffic contained within Azure"
   Your response: "Perfect! I'll design an Azure-only architecture. [proceed to next step or confirmation]"
   ❌ WRONG: Asking "Do you need on-premises connectivity?" again

3. FOLLOW-UP (if needed): Ask ONLY if critical architectural decision that wasn't already answered
   - Only ask about things that significantly change the design
   - Skip questions about traffic, regions, standard features
   - CHECK HISTORY: Has this been answered? If yes, don't ask

4. AFTER 1-2 EXCHANGES: Summarize ALL assumptions and ask for confirmation
   Example: "Perfect! Here's what I'll create:
   - Azure App Service (web tier)
   - Azure SQL Database (data tier)  
   - Redis Cache (caching layer)
   - VNet with NSGs (security)
   - East US region
   
   Should I proceed with generating the architecture diagram?"

4. ON CONFIRMATION: Respond with "CONFIRMED: <summary>" (plain text summary, NOT JSON)

OUTPUT FORMAT: Always respond with natural conversational text. NEVER output JSON, XML, or code.

Remember: The goal is to get to confirmation in 2-3 messages MAXIMUM!
""",
    tools=[]
)

diagram_agent = chat_client.create_agent(
    name="DiagramAgent",
    instructions="""You are a technical diagram generator specialized in creating DrawIO XML format diagrams for Azure cloud infrastructure.

Your role is to generate valid, well-formed XML documents that represent Azure architecture diagrams. You will receive requirements and technical specifications, then output structured XML following the DrawIO format specification.

Output format requirements:
- Start with <mxfile> root element
- Include <diagram> and <mxGraphModel> structure
- Use <mxCell> elements for components
- Include proper geometry (x, y, width, height)
- Use parent-child relationships via parent attributes
- Include edge connections between components

Technical constraints:
- CRITICAL: Use ONLY the exact icon paths provided in the prompt (already resolved from azure_icons.json)
- NEVER generate or modify icon paths (image=...) - copy them exactly as given
- If a service uses "shape=rectangle" style (no icon), keep it as is
- Use proper Azure service names and connections
- Follow hierarchical structure: Regions contain VNets, VNets contain Subnets
- Include Private Endpoints for PaaS services

Output only the raw XML content without any wrapping, explanations, or markdown formatting.""",
    tools=[]
)

review_agent = chat_client.create_agent(
    name="ReviewAgent",
    instructions="""You are a diagram quality reviewer specialized in validating DrawIO XML diagrams for Azure architectures.

Your role is to review generated diagrams and identify issues with:
1. SIZE ISSUES: Check if VNets, Regions, or containers have excessive dimensions (VNets should be ~280x280, not 320+)
2. ALIGNMENT: Verify elements are properly aligned and spaced
3. BOUNDARY VIOLATIONS: Ensure all elements fit within parent containers
4. ICON SIZES: Check if icons are reasonably sized (typically 50x60, not 80x80+)
5. OVERLAP: Identify any overlapping elements that would look messy

Output format:
- Start with either "APPROVED" or "NEEDS_REVISION"
- If NEEDS_REVISION, list specific issues with element IDs and suggested dimension fixes
- Be concise and specific

Example:
APPROVED - All elements properly sized and aligned.

or

NEEDS_REVISION
- VNet (id=110): width="320" height="320" is too large, should be width="280" height="280"
- Region (id=100): Services extend beyond y=720 boundary""",
    tools=[]
)

analysis_agent = chat_client.create_agent(
    name="ArchitectureAnalysisAgent",
    instructions="""You are an Azure architecture analyzer. Analyze requirements and output a structured JSON specification.

CRITICAL: Be LITERAL and PRECISE with user requirements. Do NOT add extra resources or reinterpret what the user says.

Your role:
1. Map EXACT user requirements to Azure services (no more, no less)
2. Follow user's specified topology (hub-and-spoke, multi-region, etc.) EXACTLY
3. Place services in regions user specifies (do NOT redistribute or duplicate)
4. Only add standard infrastructure (VNets, NSGs) - do NOT add extra compute/data services

SERVICE SELECTION STRATEGY:
- Prefer PaaS services (App Service, Functions, Cosmos DB, SQL Database) for cloud-native applications
- Use IaaS services (Virtual Machines, AVD) when user explicitly mentions VMs, AVD, custom infrastructure, or migration scenarios
- Use hybrid (App Service + VMs) when requirements indicate both managed services and custom control

TOPOLOGY DETECTION (choose based on user's words):
- "hub-and-spoke" OR "hub and spoke" OR "hub region" OR "spoke region" → topology="hub-spoke"
- Single region mentioned → topology="single-region"
- Multiple independent regions → topology="multi-region"
- Default for web apps: topology="single-region"

HUB-AND-SPOKE RULES (ONLY apply if topology="hub-spoke"):
- If user says "US is the hub with 4 AVD VMs" → Place 4 AVD VMs ONLY in US region, NOT in spoke regions
- If user says "spoke regions have 1 proxy VM" → Place 1 proxy VM ONLY in each spoke, NOT in hub
- Hub services are SHARED by spokes (do NOT duplicate them in each spoke)
- Spokes connect TO hub, they don't contain copies of hub services

MULTI-REGION RULES (ONLY apply if topology="multi-region"):
- Each region has its OWN complete set of services (App Service, database, cache per region)
- Services are REPLICATED across regions for redundancy
- Use global load balancer (Front Door, Traffic Manager) to distribute traffic

Output ONLY valid JSON with this structure:
{
  "regions": [
    {"name": "East US", "services": [...]}
  ],
  "topology": "single-region" | "multi-region" | "hub-spoke",
  "services": [
    {
      "id": "app-fe",
      "type": "App_Services",
      "name": "Web App",
      "layer": "application" | "data" | "security" | "monitoring" | "integration",
      "location": "subnet" | "region" | "global",
      "region_index": 0
    }
  ],
  "connections": [
    {"from": "app-fe", "to": "cosmos-db", "type": "solid"},
    {"from": "app-fe", "to": "app-insights", "type": "dashed"}
  ],
  "security": {
    "use_private_endpoints": true,
    "use_nsgs": true
  }
}

LOCATION RULES:
- "subnet": 
  * Compute: App Service, Azure Functions, AKS, Virtual Machines, AVD VMs
  * Proxies/VMs: Custom proxy VMs, bastion hosts, jump boxes
  * Network: Application Gateway, Load Balancer, Azure Firewall, VPN Gateway
  * Private Endpoint (MUST use type="Private Endpoint" for PaaS private connectivity)
- "region": PaaS data/AI services that sit outside VNet
  * Data: Cosmos DB, SQL Database, Storage Account, Blob Storage, Azure Cache for Redis, Azure OpenAI, Azure AI Search
  * Security: Key Vault
- "global": Cross-region overlay services (page level, not in region)
  * Identity: Managed Identity, Entra ID
  * Monitoring: Application Insights, Azure Monitor, Log Analytics

HUB-AND-SPOKE PATTERN:
- When user requests hub-and-spoke: Set topology="hub-spoke"
- Hub region contains shared services (AVD VMs, shared databases, etc.)
- Spoke regions contain regional services (proxies, firewalls, regional apps)
- Connections flow from spokes to hub for shared resources

LAYER RULES:
- "application": 
  * PaaS: App Service, Azure Functions, AKS, API Management
  * IaaS: Virtual Machines, AVD VMs, VM Scale Sets
- "data": 
  * PaaS: Cosmos DB, SQL Database, Azure Cache for Redis, Azure OpenAI, Azure AI Search
  * IaaS: SQL on VM, custom databases
  * Storage: Storage Account, Blob Storage
- "security": Key Vault, Private Endpoint (PE goes in PE subnet)
- "monitoring": Application Insights, Azure Monitor, Log Analytics
- "integration": Service Bus, Event Hubs, Event Grid, Logic Apps
- "network": 
  * PaaS: Application Gateway, Load Balancer, Front Door
  * IaaS: Azure Firewall, VPN Gateway, ExpressRoute Gateway, custom network appliances

SERVICE TYPE MAPPING (use exact names from azure_icons.json):
- Cloud-native web apps → "App Service"
- Serverless functions → "Functions"
- AVD VMs / Virtual Desktops / Custom VMs → "Virtual Machine"
- Azure managed firewalls → "Firewalls"
- VPN connectivity → "VPN Gateway"
- Container orchestration → "AKS"
- NoSQL database → "Azure Cosmos DB"
- Relational database → "SQL Database"

EXAMPLE 1 - Single-region web app (DEFAULT for "create a web app"):
- topology: "single-region"
- 1 region with App Service, SQL Database, Redis, Key Vault
- Services deployed in 1 region only

EXAMPLE 2 - Multi-region web app ("create web app in 3 regions for high availability"):
- topology: "multi-region"
- Each region has FULL stack: App Service, SQL Database, Redis
- Services REPLICATED in each region (3x App Service, 3x SQL DB, 3x Redis)

EXAMPLE 3 - Hub-and-Spoke ("hub-and-spoke with US hub containing AVD"):
- topology: "hub-spoke"
- US (hub): 4 AVD VMs + 1 proxy VM (shared resources)
- India (spoke): 1 proxy VM only (NO AVD VMs)
- Singapore (spoke): 1 proxy VM only (NO AVD VMs)
- EMEA (spoke): 1 proxy VM only (NO AVD VMs)
- Connections: Spoke proxies → Hub AVD VMs

CONNECTION TYPES:
- "solid": Data flow, API calls, direct dependencies
- "dashed": Monitoring, logging, telemetry

Map service names to azure_icons.json keys exactly as they appear in the file:
- "App Service" (not App_Services)
- "Azure Functions" (not Function_Apps)
- "Cosmos DB"
- "Azure OpenAI"
- "Storage Account" or "Blob Storage"
- "Azure Cache for Redis" or "Redis"
- "Key Vault"
- "Application Insights"
- "Azure Monitor"
- "Managed Identity"
- "AKS" or "Azure Kubernetes Service"

DO NOT include infrastructure elements as services:
- NSG (Network Security Groups) - automatically added to all subnets
- Subnet icons - subnets are containers, not services
- VNet icons - VNet is a container, not a service

Be specific and comprehensive.""",
    tools=[]
)

# Create Sequential Workflow
workflow = SequentialBuilder().participants([requirements_agent, diagram_agent]).build()


def build_dynamic_diagram_prompt(architecture: dict, azure_icons: dict, requirements_summary: str) -> str:
    """Build a dynamic diagram prompt based on analyzed architecture with proper hierarchical layout."""
    
    num_regions = len(architecture.get('regions', []))
    num_services = len(architecture.get('services', []))
    topology = architecture.get('topology', 'single-region')
    
    # Calculate layout parameters
    region_width = 480
    region_height = 480
    region_spacing = 70
    region_start_x = 50
    region_start_y = 240
    
    vnet_width = 280
    vnet_height = 280
    vnet_offset_x = 50
    vnet_offset_y = 80
    
    subnet_width = 165
    subnet_height = 150
    
    # Build hierarchical structure with proper parent-child relationships
    region_specs = []
    vnet_specs = []
    subnet_specs = []
    service_specs = []
    
    for i, region in enumerate(architecture.get('regions', [])):
        region_x = region_start_x + i * (region_width + region_spacing)
        region_id = f"region{i+1}"
        
        # Escape XML special characters in region name
        region_name_escaped = (region['name']
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
        
        region_specs.append(f"""<mxCell id="{region_id}" value="{region_name_escaped}" style="rounded=1;whiteSpace=wrap;fillColor={'#ffe6cc' if i % 2 == 0 else '#dae8fc'};strokeColor=#888888;fontSize=14;fontStyle=1;align=left;verticalAlign=top;spacing=10;" vertex="1" parent="1">
  <mxGeometry x="{region_x}" y="{region_start_y}" width="{region_width}" height="{region_height}" as="geometry"/>
</mxCell>""")
        
        # Create VNet inside region with RELATIVE coordinates
        vnet_id = f"vnet{i+1}"
        vnet_specs.append(f"""<mxCell id="{vnet_id}" value="VNet" style="rounded=0;whiteSpace=wrap;fillColor=#e1f5fe;strokeColor=#01579b;fontSize=12;fontStyle=1;align=left;verticalAlign=top;spacing=5;" vertex="1" parent="{region_id}">
  <mxGeometry x="{vnet_offset_x}" y="{vnet_offset_y}" width="{vnet_width}" height="{vnet_height}" as="geometry"/>
</mxCell>""")
        
        # Create subnets inside VNet with RELATIVE coordinates
        # Three subnets with embedded NSG icons - sized to fit within VNet (280x280)
        subnet_configs = [
            {"id": f"subnet{i+1}_app", "label": "App Subnet", "x": 10, "y": 30, "width": 125, "height": 230},
            {"id": f"subnet{i+1}_pe", "label": "Private Endpoints Subnet", "x": 145, "y": 30, "width": 125, "height": 110},
            {"id": f"subnet{i+1}_gateway", "label": "Gateway Subnet", "x": 145, "y": 150, "width": 125, "height": 110}
        ]
        
        for subnet_config in subnet_configs:
            subnet_id = subnet_config['id']
            
            # Escape XML special characters in subnet label
            subnet_label_escaped = (subnet_config['label']
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))
            
            # Add subnet container
            subnet_specs.append(f"""<mxCell id="{subnet_id}" value="{subnet_label_escaped}" style="rounded=0;whiteSpace=wrap;fillColor=#fff4e6;strokeColor=#d79b00;fontSize=10;align=left;verticalAlign=top;spacing=3;" vertex="1" parent="{vnet_id}">
  <mxGeometry x="{subnet_config['x']}" y="{subnet_config['y']}" width="{subnet_config['width']}" height="{subnet_config['height']}" as="geometry"/>
</mxCell>""")
            
            # Add small NSG icon in top-right corner of subnet (decorative)
            nsg_icon = azure_icons.get("NSG") or azure_icons.get("Network Security Groups")
            if nsg_icon:
                subnet_specs.append(f"""<mxCell id="{subnet_id}_nsg" style="shape=image;image={nsg_icon};fontSize=7;" vertex="1" parent="{subnet_id}">
  <mxGeometry x="100" y="3" width="20" height="20" as="geometry"/>
</mxCell>""")
            else:
                # Use small rectangle if NSG icon not found
                subnet_specs.append(f"""<mxCell id="{subnet_id}_nsg" value="NSG" style="shape=rectangle;fillColor=#fff3cd;strokeColor=#ffc107;strokeWidth=1;fontSize=6;" vertex="1" parent="{subnet_id}">
  <mxGeometry x="100" y="3" width="20" height="20" as="geometry"/>
</mxCell>""")
    
    # Count services by type for layout calculation
    services_by_location = {}
    for service in architecture.get('services', []):
        region_idx = service.get('region_index', 0)
        layer = service.get('layer', 'application')
        location = service.get('location', 'region')
        
        # Create counters for each location type
        key = f"{region_idx}_{location}_{layer}"
        if key not in services_by_location:
            services_by_location[key] = 0
    
    # Build service specifications with proper parent assignment
    service_counters = {}
    missing_icons = []  # Track missing icons for console output
    
    for service in architecture.get('services', []):
        # CRITICAL: Only use icon paths from azure_icons.json, NEVER hallucinate paths
        service_type = service['type']
        icon_path = None
        search_attempts = []
        
        # Step 1: Try exact match in azure_icons.json
        search_attempts.append(service_type)
        if service_type in azure_icons:
            icon_path = azure_icons[service_type]
        
        # Step 2: Try with underscore replaced by space
        if not icon_path:
            service_type_clean = service_type.replace('_', ' ')
            search_attempts.append(service_type_clean)
            if service_type_clean in azure_icons:
                icon_path = azure_icons[service_type_clean]
        
        # Step 3: Try common variations (remove Azure prefix, etc.)
        if not icon_path:
            service_type_alt = service_type.replace('Azure ', '').replace('azure ', '')
            search_attempts.append(service_type_alt)
            if service_type_alt in azure_icons:
                icon_path = azure_icons[service_type_alt]
        
        # Step 4: Try case-insensitive search in azure_icons keys
        if not icon_path:
            service_type_lower = service_type.lower()
            for key in azure_icons.keys():
                if key.lower() == service_type_lower:
                    icon_path = azure_icons[key]
                    search_attempts.append(f"{key} (case-insensitive match)")
                    break
        
        # Step 5: If still not found, use rectangle and log it
        if not icon_path:
            style_suffix = "shape=rectangle;fillColor=#e3f2fd;strokeColor=#1976d2;strokeWidth=2"
            missing_icons.append({
                'service_id': service['id'],
                'requested_type': service_type,
                'searched': search_attempts
            })
        else:
            style_suffix = f"shape=image;image={icon_path}"
            
        region_idx = service.get('region_index')
        if region_idx is None:
            region_idx = 0  # Default to first region if not specified
        
        layer = service.get('layer', 'application')
        location = service.get('location', 'region')
        service_name = service.get('name', service['id'])
        service_id = service['id']
        
        # Determine parent and position based on service type
        if location == 'global':
            # Global services (identity, monitoring) at page level
            parent = "1"
            counter_key = f"global_{layer}"
            if counter_key not in service_counters:
                service_counters[counter_key] = 0
            
            if layer == 'monitoring':
                x = 600 + (service_counters[counter_key] % 2) * 70
                y = 120 + (service_counters[counter_key] // 2) * 70
            else:  # identity
                x = 600
                y = 50
            service_counters[counter_key] += 1
            
        elif location == 'subnet':
            # Determine which subnet based on layer
            if layer == 'application':
                # App services in App Subnet
                parent = f"subnet{region_idx+1}_app"
                counter_key = f"{region_idx}_app"
            elif layer == 'security' or 'private endpoint' in service_name.lower() or service_type == 'Private Endpoint':
                # Private Endpoints in PE Subnet
                parent = f"subnet{region_idx+1}_pe"
                counter_key = f"{region_idx}_pe"
            elif layer == 'network':
                # Network infrastructure (App Gateway, Firewall, Load Balancer) in Gateway Subnet
                parent = f"subnet{region_idx+1}_gateway"
                counter_key = f"{region_idx}_gateway"
            else:
                # Integration services (Service Bus, Event Hub) also in Gateway Subnet
                parent = f"subnet{region_idx+1}_gateway"
                counter_key = f"{region_idx}_gateway"
            
            if counter_key not in service_counters:
                service_counters[counter_key] = 0
            
            # Grid layout inside subnet (adjusted for narrower 125px subnets)
            col = service_counters[counter_key] % 2
            row = service_counters[counter_key] // 2
            x = 15 + col * 60  # Reduced spacing from 80 to 60 for 125px subnet width
            y = 30 + row * 80
            service_counters[counter_key] += 1
            
        else:  # region level - PaaS data services
            parent = f"region{region_idx+1}"
            counter_key = f"{region_idx}_region_{layer}"
            
            if counter_key not in service_counters:
                service_counters[counter_key] = 0
            
            # Position outside VNet on the right side (max x = 410 to stay within 480 width)
            if layer == 'data':
                x = 360  # Right side of region, inside boundary
                y = 90 + service_counters[counter_key] * 70
            elif layer == 'security':
                x = 10
                y = 30
            else:  # other region-level services
                x = 360  # Right side of region, inside boundary
                y = 30 + service_counters[counter_key] * 70
            
            service_counters[counter_key] += 1
        
        # Escape XML special characters in service name
        service_name_escaped = (service_name
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))
        
        service_specs.append(f"""<mxCell id="{service_id}" value="{service_name_escaped}" style="{style_suffix};fontSize=9;fontColor=#000000;labelPosition=center;verticalLabelPosition=bottom;align=center;verticalAlign=top;spacingTop=2;" vertex="1" parent="{parent}">
  <mxGeometry x="{x}" y="{y}" width="50" height="50" as="geometry"/>
</mxCell>""")
    
    # Build connection specifications
    connection_specs = []
    for i, conn in enumerate(architecture.get('connections', [])):
        style = "dashed=1" if conn.get('type') == 'dashed' else ""
        connection_specs.append(f"""<mxCell id="edge{i+1}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;strokeColor=#0000ff;strokeWidth=2;{style};endArrow=block;endFill=1" edge="1" source="{conn['from']}" target="{conn['to']}" parent="1">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>""")
    
    prompt = f"""Generate a DrawIO XML diagram for this Azure architecture.

Requirements: {requirements_summary}

Architecture Summary:
- Topology: {topology}
- Regions: {num_regions}
- Services: {num_services}

CRITICAL RULES FOR PARENT-CHILD RELATIONSHIPS:
1. Regions have parent="1" (page level) with ABSOLUTE coordinates
2. VNets have parent="regionX" with RELATIVE coordinates to region
3. Subnets have parent="vnetX" with RELATIVE coordinates to VNet
4. Services have parent="subnetX" or parent="regionX" with RELATIVE coordinates
5. All child elements use coordinates RELATIVE to their parent container
6. Never use absolute page coordinates for elements inside containers

SIZE CONSTRAINTS:
- Region: 480x480
- VNet: 380x360 (inside region)
- Subnet: 160x240 (inside VNet)
- Service icon: 50x50
- Private Endpoint: 30x30
- NSG: 20x20

XML STRUCTURE TEMPLATE:
```xml
<mxfile host="app.diagrams.net">
  <diagram name="Azure Architecture">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <!-- All elements below -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

USE THESE EXACT ELEMENT DEFINITIONS - COPY EXACTLY:

REGIONS (parent="1", absolute coordinates):
{''.join(region_specs)}

VNETs (parent="regionX", relative coordinates inside region):
{''.join(vnet_specs)}

SUBNETs (parent="vnetX", relative coordinates inside VNet):
{''.join(subnet_specs)}

SERVICES (parent="subnetX" or "regionX", relative coordinates):
{''.join(service_specs)}

CONNECTIONS (source and target are service IDs):
{''.join(connection_specs)}

ARCHITECTURE LAYOUT STRUCTURE:
- Region contains VNet + PaaS data services (outside VNet, on the right) + identity services
- VNet contains 3 subnets (each subnet has NSG icon in top-right corner):
  * App Subnet: App Service, Azure Functions, compute workloads
  * Private Endpoints Subnet: All Private Endpoints for secure PaaS connectivity
  * Gateway Subnet: Application Gateway, Load Balancer, Azure Firewall, network infrastructure
- ALL services MUST be inside a region - NEVER place services at global level outside regions

IMPORTANT RULES:
1. DO NOT add separate NSG, Subnet, or VNet service boxes - they are infrastructure already in the layout
2. NSGs are automatically added as small icons in subnet corners
3. Subnets and VNets are containers, not services
4. Only add actual compute, data, and application services from the service specs

INSTRUCTIONS:
1. Copy ALL elements EXACTLY as provided above - do not modify anything
2. DO NOT change coordinates - they prevent overlapping
3. DO NOT change parent attributes - they define proper nesting
4. Add all connection edges between services
5. Ensure all mxCell tags are properly closed
6. Use exact icon paths from service specifications
7. Private Endpoints MUST be in the PE subnet with connections to their PaaS services
8. Do NOT create extra VNet, Subnet, or NSG service boxes
9. Output ONLY the complete XML - no explanations

Output the complete DrawIO XML now."""
    
    # Log missing icons to console for visibility
    if missing_icons:
        print(f"\n{'='*80}")
        print(f"⚠️  MISSING ICONS - Using Rectangle Placeholders")
        print(f"{'='*80}")
        for missing in missing_icons:
            print(f"  Service: {missing['service_id']}")
            print(f"  Requested Type: {missing['requested_type']}")
            print(f"  Searched: {', '.join(missing['searched'])}")
            print(f"  → Using rectangle placeholder")
            print()
        print(f"{'='*80}\n")
    
    return prompt


async def process_conversation_async(message: str, session_id: Optional[str] = None, history: Optional[List[Dict]] = None, save_to_file: bool = False) -> Dict:
    """
    Process conversational input using Microsoft Agent Framework Sequential Orchestration
    
    Two agents in sequence:
    1. Requirements Agent - Validates and confirms requirements with user
    2. Diagram Agent - Generates XML once requirements are confirmed
    
    Args:
        message: User's current message
        session_id: Session identifier for conversation tracking
        save_to_file: If True, saves diagram to file (useful for console/testing only)
        history: Previous conversation history
        
    Returns:
        Dict with either:
        - {"type": "message", "content": str, "session_id": str} for conversation
        - {"type": "diagram", "xml": str, "session_id": str} for final output
    """
    # Generate or retrieve session
    if not session_id:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "state": "gathering",  # gathering, generating
            "requirements": {},
            "history": []
        }
        logger.info(f"[{session_id}] Created new session")
    
    # Ensure session exists in sessions dict
    if session_id not in sessions:
        sessions[session_id] = {
            "state": "gathering",
            "requirements": {},
            "history": []
        }
        logger.info(f"[{session_id}] Recreated missing session")
    
    session = sessions[session_id]
    
    # During gathering phase, use only requirements agent
    if session["state"] == "gathering":
        logger.info(f"[{session_id}] Starting requirements gathering phase")
        print(f"\n{'='*80}")
        print(f"📝 REQUIREMENTS GATHERING - Session: {session_id[:8]}")
        print(f"{'='*80}\n")
        start_time = time.time()
        
        # Add current message to history
        session["history"].append({"role": "user", "content": message})
        logger.info(f"[{session_id}] User message: {message[:100]}...")
        
        # Convert history to proper format for agent
        from agent_framework import ChatMessage, Role
        
        messages = []
        for msg in session["history"]:
            role = Role.USER if msg["role"] == "user" else Role.ASSISTANT
            messages.append(ChatMessage(role=role, text=msg["content"]))
        
        # Run requirements agent with full conversation history
        logger.info(f"[{session_id}] Calling requirements agent...")
        agent_start = time.time()
        result = await requirements_agent.run(messages)
        agent_duration = time.time() - agent_start
        logger.info(f"[{session_id}] Requirements agent completed in {agent_duration:.2f}s")
        
        response = result.text if hasattr(result, 'text') else str(result)
        
        # CRITICAL: Filter out any JSON/code responses from requirements agent
        # Requirements agent should ONLY return conversational text
        response_stripped = response.strip()
        
        # Debug logging
        logger.info(f"[{session_id}] Requirements agent response preview: {response_stripped[:100]}...")
        
        if response_stripped.startswith('{') or response_stripped.startswith('[') or '```json' in response or '```' in response:
            logger.warning(f"[{session_id}] ⚠️ Requirements agent returned JSON/code - rejecting and asking again")
            # Inject a correction message
            correction_msg = "Please provide a conversational response, not JSON or code. Ask clarifying questions or summarize requirements in plain English."
            messages.append(ChatMessage(role=Role.USER, text=correction_msg))
            
            # Retry with correction
            result = await requirements_agent.run(messages)
            response = result.text if hasattr(result, 'text') else str(result)
            response_stripped = response.strip()
            
            # If still returning JSON, force a generic response
            if response_stripped.startswith('{') or response_stripped.startswith('[') or '```' in response:
                logger.error(f"[{session_id}] Requirements agent still returning JSON after correction")
                response = "I understand your requirements. Let me confirm what we'll build and then generate the architecture diagram. Please confirm if you'd like to proceed."
        
        session["history"].append({"role": "assistant", "content": response})
        
        # Check if user confirmed OR agent confirmed with "CONFIRMED:"
        # ONLY check for confirmation if we already have some conversation history (not first message)
        user_confirmed = False
        agent_confirmed = "CONFIRMED:" in response
        
        # Only consider user confirmation keywords if this is NOT the first message
        # First message is always a request, not a confirmation
        if len(session["history"]) > 2:  # More than just this exchange
            user_confirmed = any(keyword in message.lower() for keyword in ["yes", "approved", "confirmed", "proceed", "go ahead", "sure", "ok", "okay"])
        
        logger.info(f"[{session_id}] User confirmed: {user_confirmed}, Agent confirmed: {agent_confirmed}, History length: {len(session['history'])}")
        
        if user_confirmed or agent_confirmed:
            session["state"] = "generating"
            # Extract requirements from response (after CONFIRMED:)
            if agent_confirmed:
                try:
                    confirmed_text = response.split("CONFIRMED:")[1].strip()
                    session["requirements"] = {"summary": confirmed_text}
                except:
                    session["requirements"] = {"summary": response}
            else:
                # User confirmed directly, use last assistant message as requirements
                session["requirements"] = {"summary": response}
        
        sessions[session_id] = session
        
        # If user confirmed, immediately trigger diagram generation instead of returning message
        if user_confirmed and not agent_confirmed:
            # Skip returning the message and go straight to diagram generation
            session["state"] = "generating"
            sessions[session_id] = session
            # Fall through to generating state
        else:
            return {
                "type": "message",
                "content": response,
                "session_id": session_id,
                "state": session["state"]
            }
    
    # Once confirmed, run ONLY the diagram agent (not the workflow)
    if session["state"] == "generating":
        logger.info(f"[{session_id}] Starting diagram generation phase")
        print(f"\n{'='*80}")
        print(f"🎨 DIAGRAM GENERATION - Session: {session_id[:8]}")
        print(f"{'='*80}\n")
        diagram_start = time.time()
        
        # Load azure_icons.json and reference diagram
        logger.info(f"[{session_id}] Loading azure_icons.json and reference diagram...")
        tools_dir = Path(__file__).parent / "tools"
        azure_icons = json.loads((tools_dir / "azure_icons.json").read_text())
        
        # Load reference diagram as example
        reference_path = tools_dir / "reference.drawio"
        reference_xml = reference_path.read_text(encoding='utf-8') if reference_path.exists() else ""
        
        # Include azure_icons directly in the context for the agent
        icon_list = json.dumps(azure_icons, indent=2)
        
        # STEP 1: Analyze architecture requirements
        logger.info(f"[{session_id}] Analyzing architecture...")
        
        # Provide available Azure services from azure_icons.json
        available_services = list(azure_icons.keys())
        services_list = ', '.join(available_services[:20]) + f"... ({len(available_services)} total)"
        
        analysis_prompt = f"""Analyze these requirements and output JSON architecture specification:

{session["requirements"]["summary"]}

Available Azure services in azure_icons.json:
{', '.join(available_services)}

CRITICAL: Use EXACT service names from the list above in the "type" field.
Common mappings:
- Web apps → "App Service" (not "Web App", "AppService", or "App_Services")
- Serverless → "Azure Functions" (not "Function_Apps" or "Functions")
- NoSQL database → "Cosmos DB" (not "Azure_Cosmos_DB" or "CosmosDB")
- Vector store → "Cosmos DB" or "Blob Storage" (not "Vector_Store")
- LLM/AI → "Azure OpenAI" (not "OpenAI" or "Azure_OpenAI")
- Object storage → "Storage Account" or "Blob Storage" (not "Azure_Storage")
- Cache → "Azure Cache for Redis" or "Redis" (not "Cache" or "Redis_Cache")
- Secrets → "Key Vault" (not "Azure_Key_Vault" or "KeyVault")
- Monitoring → "Application Insights" (not "App_Insights" or "AppInsights")
- Search → "Cognitive Search" or "AI Search" (not "Azure_Search" or "Search_Service")

If the exact name isn't in the list, find the CLOSEST MATCH from the available services.

Output ONLY the JSON structure as specified in your instructions."""
        
        try:
            analysis_result = await asyncio.wait_for(analysis_agent.run(analysis_prompt), timeout=60.0)
            analysis_text = analysis_result.text if hasattr(analysis_result, 'text') else str(analysis_result)
            
            # Clean JSON if wrapped in markdown FIRST before checking
            if "```json" in analysis_text:
                analysis_text = analysis_text.split("```json")[1].split("```")[0].strip()
            elif "```" in analysis_text:
                analysis_text = analysis_text.split("```")[1].split("```")[0].strip()
            
            # Check if the agent is asking for clarification (more robust check)
            stripped = analysis_text.strip()
            looks_like_json = (stripped.startswith('{') or stripped.startswith('[')) and ('"regions"' in stripped or '"services"' in stripped)
            
            if not looks_like_json:
                # Agent is asking questions, not returning JSON
                logger.info(f"[{session_id}] Analysis agent asking for clarification")
                return {"type": "message", "content": stripped, "session_id": session_id}
            
            architecture = json.loads(analysis_text)
            logger.info(f"[{session_id}] Architecture analyzed: {len(architecture.get('services', []))} services, {len(architecture.get('regions', []))} regions")
            
        except asyncio.TimeoutError:
            logger.error(f"[{session_id}] Analysis timeout!")
            return {"type": "error", "message": "Architecture analysis timed out.", "session_id": session_id}
        except json.JSONDecodeError as e:
            logger.error(f"[{session_id}] Invalid JSON from analysis: {e}")
            logger.error(f"Analysis output: {analysis_text[:500]}")
            return {"type": "error", "message": "Failed to analyze architecture.", "session_id": session_id}
        except Exception as e:
            logger.error(f"[{session_id}] Analysis error: {str(e)}", exc_info=True)
            return {"type": "error", "message": f"Analysis failed: {str(e)}", "session_id": session_id}
        
        # STEP 2: Generate dynamic diagram prompt based on analysis
        logger.info(f"[{session_id}] Building dynamic diagram prompt...")
        try:
            diagram_prompt = build_dynamic_diagram_prompt(architecture, azure_icons, session["requirements"]["summary"])
            logger.info(f"[{session_id}] Diagram prompt built successfully ({len(diagram_prompt)} chars)")
        except Exception as e:
            logger.error(f"[{session_id}] Error building diagram prompt: {str(e)}", exc_info=True)
            return {"type": "error", "message": f"Failed to build diagram prompt: {str(e)}", "session_id": session_id}
        
        # STEP 3: Generate diagram
        logger.info(f"[{session_id}] Generating diagram (may take 60-90 seconds)...")
        
        try:
            result = await asyncio.wait_for(diagram_agent.run(diagram_prompt), timeout=180.0)
            xml_content = result.text if hasattr(result, 'text') else str(result)
            
            logger.info(f"[{session_id}] Received response ({len(xml_content)} chars)")
            logger.info(f"[{session_id}] First 200 chars: {xml_content[:200]}")
            
            # Clean XML if wrapped in markdown
            if "```xml" in xml_content:
                xml_content = xml_content.split("```xml")[1].split("```")[0].strip()
                logger.info(f"[{session_id}] Cleaned from ```xml wrapper")
            elif "```" in xml_content:
                xml_content = xml_content.split("```")[1].split("```")[0].strip()
                logger.info(f"[{session_id}] Cleaned from ``` wrapper")
            
            # Basic XML structure validation
            if not xml_content.strip().startswith('<mxfile'):
                logger.error(f"[{session_id}] Invalid XML - doesn't start with <mxfile>")
                logger.error(f"XML preview: {xml_content[:200]}")
                return {"type": "error", "message": "Generated diagram has invalid structure. Please try again.", "session_id": session_id}
            
            if '</mxfile>' not in xml_content:
                logger.error(f"[{session_id}] Invalid XML - missing closing </mxfile>")
                return {"type": "error", "message": "Generated diagram is incomplete. Please try again.", "session_id": session_id}
            
            # Review the diagram for size and alignment issues
            logger.info(f"[{session_id}] Reviewing diagram quality...")
            review_prompt = f"""Review this DrawIO XML diagram:

{xml_content[:3000]}...

Check for:
1. VNet dimensions (should be 280x280, NOT 320x320 or larger)
2. Service icon sizes (should be 50x60, NOT 80x80 or larger)  
3. Region dimensions (should be 480x480)
4. Proper alignment and spacing
5. All elements within boundaries

Provide verdict: APPROVED or NEEDS_REVISION with specific issues."""
            
            review_result = await asyncio.wait_for(review_agent.run(review_prompt), timeout=30.0)
            review_text = review_result.text if hasattr(review_result, 'text') else str(review_result)
            logger.info(f"[{session_id}] Review: {review_text[:200]}...")
            
            if "NEEDS_REVISION" in review_text:
                logger.warning(f"[{session_id}] ⚠️ Diagram needs revision: {review_text}")
            else:
                logger.info(f"[{session_id}] ✅ Diagram approved")
            
            # Strict validation - reject broken diagrams instead of sending to UI
            import re
            validation_errors = []
            
            # Check 0: Verify region count matches requirements
            region_count = len(re.findall(r'<mxCell id="region\d+"', xml_content))
            required_regions = architecture.get('regions', [])
            if len(required_regions) != region_count:
                validation_errors.append(f"Requirements specify {len(required_regions)} regions {[r.get('name', 'Unknown') for r in required_regions]} but diagram has {region_count} regions. You MUST create exactly {len(required_regions)} region containers.")
            
            # Check 1: Multi-region diagrams - detect services that should be global based on context
            if 'region2' in xml_content:
                # Pattern: Find services at parent="region1" or parent="region2"
                regional_services_pattern = r'<mxCell id="([^"]+)"[^>]*parent="region[12]"[^>]*value="([^"]*)"'
                regional_services = re.findall(regional_services_pattern, xml_content)
                
                for service_id, service_label in regional_services:
                    # Skip containers
                    if any(skip in service_id.lower() for skip in ['region', 'vnet', 'subnet']):
                        continue
                    
                    # Check if this service appears in BOTH regions with similar names
                    # If it doesn't, it might be a global service incorrectly placed in one region
                    service_base = service_id.replace('-east', '').replace('-west', '').replace('-1', '').replace('-2', '')
                    
                    # Check if service name or label suggests it's global (Front Door, Traffic Manager, etc.)
                    global_keywords = ['front door', 'traffic manager', 'global', 'cdn', 'waf']
                    if any(keyword in service_label.lower() or keyword in service_id.lower() for keyword in global_keywords):
                        validation_errors.append(f"Multi-region load balancer '{service_id}' should be at global level (parent='1'), not in single region")
            
            # Check 2: Services must not exceed region boundaries
            region_pattern = r'<mxCell id="([^"]+)"[^>]*parent="region\d+"[^>]*>\s*<mxGeometry[^>]*x="(\d+)"'
            for match in re.finditer(region_pattern, xml_content):
                service_id = match.group(1)
                x = int(match.group(2))
                if 'region' not in service_id and 'vnet' not in service_id and x > 410:
                    validation_errors.append(f"Service '{service_id}' at x={x} exceeds region boundary")
            
            # Check 3: Services at parent="1" (except regions and truly global services)
            global_pattern = r'<mxCell id="([^"]+)"[^>]*parent="1"[^>]*value="([^"]*)"[^>]*>\s*<mxGeometry[^>]*x="(\d+)"'
            for match in re.finditer(global_pattern, xml_content):
                service_id = match.group(1)
                service_label = match.group(2)
                x = int(match.group(3))
                
                # Skip region containers
                if 'region' in service_id.lower():
                    continue
                
                # Check if service should be allowed at global level based on its characteristics
                global_keywords = ['front door', 'traffic manager', 'cdn', 'global', 'monitor', 'application insights']
                is_global_service = any(keyword in service_label.lower() or keyword in service_id.lower() for keyword in global_keywords)
                
                # Also allow if it's positioned in the global area (x >= 550)
                is_in_global_position = x >= 550
                
                # Flag if service is at global level but shouldn't be
                if not is_global_service and not is_in_global_position and x > 100:
                    validation_errors.append(f"Service '{service_id}' at global level (should be in region)")
            
            # Auto-retry until diagram is valid (no limit, will continue until success)
            retry_count = 0
            
            while validation_errors:
                retry_count += 1
                print(f"\n{'='*80}")
                print(f"⚠️  VALIDATION FAILED - Retry Attempt #{retry_count}")
                print(f"{'='*80}")
                logger.warning(f"[{session_id}] ⚠️ Validation failed, retry attempt #{retry_count}...")
                
                for err in validation_errors:
                    print(f"   ❌ {err}")
                    logger.warning(f"  {err}")
                
                print(f"\n🔄 Regenerating diagram with corrections...")
                print(f"{'='*80}\n")
                
                # Build corrective instructions with escalating severity
                correction_notes = "\n".join([f"- {err}" for err in validation_errors])
                
                # Escalate correction intensity based on retry count
                if retry_count == 1:
                    severity = "CRITICAL CORRECTIONS NEEDED"
                    instruction = """
FIXES REQUIRED:
1. For multi-region: Place Front Door / Traffic Manager at parent="1" (global level), NOT in region1 or region2
2. Services in regions MUST have x <= 360 (region width is 480, leave margin for labels)
3. Global services (frontdoor, traffic_manager, azure-monitor) should have parent="1" and x >= 550
4. Regional services should have parent="regionX" and x <= 360
"""
                elif retry_count == 2:
                    severity = "⚠️ URGENT - SECOND ATTEMPT - YOU MUST FIX THESE ERRORS"
                    instruction = """
YOU ARE REPEATING THE SAME MISTAKES! Follow these EXACT rules:

EXAMPLE CORRECTIONS:

❌ WRONG - Front Door in single region:
<mxCell id="frontdoor" ... parent="region1">
  <mxGeometry x="360" y="50" .../>

✅ CORRECT - Front Door at global level:
<mxCell id="frontdoor" ... parent="1">
  <mxGeometry x="550" y="50" .../>

❌ WRONG - Service exceeding region boundary:
<mxCell id="openai-east" ... parent="region1">
  <mxGeometry x="445" y="90" .../>

✅ CORRECT - Service inside region boundary:
<mxCell id="openai-east" ... parent="region1">
  <mxGeometry x="360" y="90" .../>

RULES (MANDATORY):
- Multi-region load balancers: parent="1", x >= 550
- Regional services: parent="regionX", x <= 360
- NO exceptions!
"""
                else:
                    severity = f"🚨 CRITICAL FAILURE - ATTEMPT #{retry_count} - STOP REPEATING ERRORS!"
                    instruction = f"""
YOU HAVE FAILED {retry_count-1} TIMES WITH THE SAME MISTAKES!

THIS IS YOUR FINAL INSTRUCTION SET - FOLLOW IT EXACTLY:

STEP 1: IDENTIFY THE PROBLEM SERVICES
{correction_notes}

STEP 2: FOR EACH ERROR ABOVE, APPLY THESE FIXES:

If error says "load balancer should be at global level":
   → Change parent="region1" to parent="1"
   → Change x coordinate to 550 or higher
   → Example: <mxCell id="frontdoor" parent="1"><mxGeometry x="550" y="50" .../></mxCell>

If error says "exceeds region boundary":
   → Keep parent="regionX" (DO NOT CHANGE)
   → Change x coordinate to 360 or lower
   → Example: <mxCell id="openai-east" parent="region1"><mxGeometry x="360" y="90" .../></mxCell>

If error says "at global level (should be in region)":
   → Change parent="1" to parent="region1"
   → Change x coordinate to 360 or lower
   → Example: <mxCell id="keyvault" parent="region1"><mxGeometry x="10" y="30" .../></mxCell>

STEP 3: GENERATE THE CORRECTED XML
- Apply ALL fixes from Step 2
- Double-check coordinates: regional services x <= 360, global services x >= 550
- Verify parent attributes match the rules above

DO NOT MAKE THE SAME MISTAKES AGAIN!
"""
                
                retry_prompt = f"""{diagram_prompt}

{'='*80}
{severity}
{'='*80}

Previous attempt had these errors:
{correction_notes}

{instruction}

Generate the CORRECTED diagram now with ALL fixes applied."""

                logger.info(f"[{session_id}] Regenerating with corrections...")
                print(f"⏳ Generating corrected diagram (this may take 60-180 seconds)...")
                result = await asyncio.wait_for(diagram_agent.run(retry_prompt), timeout=180.0)
                xml_content = result.text if hasattr(result, 'text') else str(result)
                print(f"✅ Diagram received, validating...")
                
                # Clean XML
                if "```xml" in xml_content:
                    xml_content = xml_content.split("```xml")[1].split("```")[0].strip()
                elif "```" in xml_content:
                    xml_content = xml_content.split("```")[1].split("```")[0].strip()
                
                # Re-validate with same dynamic logic
                validation_errors = []
                
                # Check 1: Multi-region load balancers
                if 'region2' in xml_content:
                    regional_services_pattern = r'<mxCell id="([^"]+)"[^>]*parent="region[12]"[^>]*value="([^"]*)"'
                    regional_services = re.findall(regional_services_pattern, xml_content)
                    
                    for service_id, service_label in regional_services:
                        if any(skip in service_id.lower() for skip in ['region', 'vnet', 'subnet']):
                            continue
                        
                        global_keywords = ['front door', 'traffic manager', 'global', 'cdn', 'waf']
                        if any(keyword in service_label.lower() or keyword in service_id.lower() for keyword in global_keywords):
                            validation_errors.append(f"Multi-region load balancer '{service_id}' should be at global level")
                
                # Check 2: Region boundary violations
                region_pattern = r'<mxCell id="([^"]+)"[^>]*parent="region\d+"[^>]*>\s*<mxGeometry[^>]*x="(\d+)"'
                for match in re.finditer(region_pattern, xml_content):
                    service_id = match.group(1)
                    x = int(match.group(2))
                    if 'region' not in service_id and 'vnet' not in service_id and x > 410:
                        validation_errors.append(f"Service '{service_id}' at x={x} exceeds region boundary")
                
                # Check 3: Services at global level
                global_pattern = r'<mxCell id="([^"]+)"[^>]*parent="1"[^>]*value="([^"]*)"[^>]*>\s*<mxGeometry[^>]*x="(\d+)"'
                for match in re.finditer(global_pattern, xml_content):
                    service_id = match.group(1)
                    service_label = match.group(2)
                    x = int(match.group(3))
                    
                    if 'region' in service_id.lower():
                        continue
                    
                    global_keywords = ['front door', 'traffic manager', 'cdn', 'global', 'monitor', 'application insights']
                    is_global_service = any(keyword in service_label.lower() or keyword in service_id.lower() for keyword in global_keywords)
                    is_in_global_position = x >= 550
                    
                    if not is_global_service and not is_in_global_position and x > 100:
                        validation_errors.append(f"Service '{service_id}' at global level")
            
            # Validation passed (loop exited)
            
            print(f"\n{'='*80}")
            print(f"✅ DIAGRAM VALIDATION PASSED")
            if retry_count > 0:
                print(f"   (Success after {retry_count} correction attempts)")
            print(f"{'='*80}\n")
            logger.info(f"[{session_id}] ✅ Diagram validation passed")
            
        except asyncio.TimeoutError:
            logger.error(f"[{session_id}] Timeout after 180 seconds!")
            return {"type": "error", "message": "Diagram generation timed out. Try simplifying your requirements.", "session_id": session_id}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{session_id}] Error: {error_msg}", exc_info=True)
            
            # Check for connection errors
            if "Connection error" in error_msg or "getaddrinfo failed" in error_msg or "ConnectError" in error_msg:
                return {
                    "type": "error", 
                    "message": "⚠️ Network connection error to Azure OpenAI. Please check:\n1. Internet connectivity\n2. Azure OpenAI endpoint URL in .env\n3. Azure OpenAI service is running\n\nTry again in a moment.",
                    "session_id": session_id
                }
            
            return {"type": "error", "message": f"Generation failed: {error_msg}", "session_id": session_id}
        # Save to file if requested
        if save_to_file:
            try:
                output_dir = Path(__file__).parent.parent / "Console-client"
                output_dir.mkdir(exist_ok=True)
                file_path = output_dir / "sample.drawio"
                file_path.write_text(xml_content, encoding='utf-8')
                logger.info(f"[{session_id}] Saved to {file_path}")
                return {"type": "diagram", "xml": xml_content, "session_id": session_id, "file_path": str(file_path)}
            except Exception as e:
                logger.warning(f"[{session_id}] Save failed: {str(e)}")
        
        # Clean up session after successful diagram generation
        if session_id in sessions:
            logger.info(f"[{session_id}] Cleaning up session after diagram generation")
            del sessions[session_id]
        
        return {"type": "diagram", "xml": xml_content, "session_id": session_id}


def calculate_monthly_cost(unit_price: float, unit: str, config: dict = None) -> float:
    """
    Calculate monthly cost based on unit price and unit type using generic conversions.
    
    Args:
        unit_price: Price per unit from Azure API
        unit: Unit of measure (e.g., 'Hour', '1 Hour', 'Month', 'GB', '10K')
        config: Optional configuration dictionary
    
    Returns:
        Monthly cost as float
    """
    if config is None:
        config = AZURE_PRICING_CONFIG
    
    unit_conversions = config.get("unit_conversions", {})
    
    # Try exact match first
    if unit in unit_conversions:
        conversion = unit_conversions[unit]
        return unit_price * conversion["multiplier"]
    
    # Try partial match (case-insensitive)
    unit_lower = unit.lower()
    for key, conversion in unit_conversions.items():
        if key.lower() in unit_lower or unit_lower in key.lower():
            return unit_price * conversion["multiplier"]
    
    # Default: assume monthly if no conversion found
    logger.warning(f"Unknown unit '{unit}' - assuming monthly pricing")
    return unit_price


async def get_azure_pricing(
    service_name: str, 
    region: str = "eastus", 
    include_multiple_skus: bool = True,
    config: dict = None
) -> dict:
    """
    Fetch real-time pricing from Azure Retail Prices API with multiple SKU options.
    
    Uses Azure Retail Prices API: https://prices.azure.com/api/retail/prices
    
    Args:
        service_name: Azure service name (e.g., "Virtual Machines", "App Service")
        region: Azure region (e.g., "eastus", "westeurope")
        include_multiple_skus: If True, returns multiple tier options (Basic, Standard, Premium)
        config: Optional configuration dictionary (uses AZURE_PRICING_CONFIG if not provided)
        
    Returns:
        Dictionary with pricing information including multiple SKU tiers
    """
    # Use provided config or default
    if config is None:
        config = AZURE_PRICING_CONFIG
    
    try:
        # Azure Retail Prices API endpoint (Official Pay-As-You-Go pricing)
        base_url = config.get("api_base_url", "https://prices.azure.com/api/retail/prices")
        timeout_seconds = config.get("api_timeout_seconds", 10)
        max_results = config.get("max_results_per_query", 20)
        
        # Use LLM to resolve service name to Azure Retail Prices API format
        meter_name = await resolve_azure_pricing_service_name(service_name)
        
        # Normalize region name for Azure ARM format
        region_normalized = region.lower().replace(' ', '')
        
        # Handle special cases for global/regional services
        # Global services like Front Door, Traffic Manager don't have region-specific pricing
        global_services = ["azure front door and cdn profiles", "front door", "traffic manager", "azure cdn"]
        is_global_service = meter_name.lower() in global_services or region_normalized in ['global', 'worldwide', 'unknown']
        
        # Filter by service and region
        # Using OData filter syntax supported by Azure Retail Prices API
        if is_global_service:
            # Global services - no region filter, just get first available pricing
            filter_query = f"serviceName eq '{meter_name}'"
            logger.info(f"Querying global service '{meter_name}' without region filter")
        else:
            filter_query = f"serviceName eq '{meter_name}' and armRegionName eq '{region_normalized}'"
        
        # Request multiple items to get different SKUs (use config value)
        top_count = max_results if include_multiple_skus else 5
        
        async with aiohttp.ClientSession() as session:
            params = {
                "$filter": filter_query,
                "$top": str(top_count)
            }
            
            async with session.get(base_url, params=params, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get('Items', [])
                    
                    if items:
                        # Group by SKU tier
                        skus = {}
                        for item in items:
                            sku_name = item.get('skuName', 'Standard')
                            if sku_name not in skus:
                                skus[sku_name] = {
                                    "service": meter_name,
                                    "region": region_normalized,
                                    "tier": sku_name,
                                    "unit_price": item.get('retailPrice', 0),
                                    "unit": item.get('unitOfMeasure', 'Hour'),
                                    "currency": item.get('currencyCode', 'USD'),
                                    "meter_name": item.get('meterName', ''),
                                    "product_name": item.get('productName', ''),
                                    "effective_date": item.get('effectiveStartDate', '')
                                }
                        
                        # Return multiple SKU options if requested
                        if include_multiple_skus and len(skus) > 1:
                            return {
                                "service": meter_name,
                                "region": region_normalized,
                                "skus": list(skus.values()),
                                "api_source": "Azure Retail Prices API"
                            }
                        else:
                            # Return first (usually base tier)
                            first_sku = list(skus.values())[0]
                            first_sku["api_source"] = "Azure Retail Prices API"
                            return first_sku
                    
                    # No items found - try alternate service names for known problematic services
                    alternate_names = {
                        "Azure Private Link": ["Private Link", "Virtual Network"],
                        "Azure Front Door and CDN profiles": ["Front Door", "Azure Front Door", "Content Delivery Network", "CDN Profile"],
                        "Azure Cognitive Search": ["Cognitive Search", "Search Services", "Azure Search"]
                    }
                    
                    if meter_name in alternate_names:
                        for alt_name in alternate_names[meter_name]:
                            # Use same logic for global services in alternate search
                            if is_global_service:
                                alt_filter = f"serviceName eq '{alt_name}'"
                            else:
                                alt_filter = f"serviceName eq '{alt_name}' and armRegionName eq '{region_normalized}'"
                            alt_params = {"$filter": alt_filter, "$top": str(top_count)}
                            
                            async with session.get(base_url, params=alt_params, timeout=aiohttp.ClientTimeout(total=timeout_seconds)) as alt_response:
                                if alt_response.status == 200:
                                    alt_data = await alt_response.json()
                                    alt_items = alt_data.get('Items', [])
                                    
                                    if alt_items:
                                        logger.info(f"Found pricing using alternate name '{alt_name}' for {meter_name}")
                                        # Return first item with alternate name
                                        item = alt_items[0]
                                        return {
                                            "service": alt_name,
                                            "region": region_normalized,
                                            "tier": item.get('skuName', 'Standard'),
                                            "unit_price": item.get('retailPrice', 0),
                                            "unit": item.get('unitOfMeasure', 'Hour'),
                                            "currency": item.get('currencyCode', 'USD'),
                                            "meter_name": item.get('meterName', ''),
                                            "product_name": item.get('productName', ''),
                                            "api_source": "Azure Retail Prices API (alternate name)"
                                        }
                
                # Fallback if no pricing found
                logger.warning(f"No pricing data found for {meter_name} in {region_normalized}")
                return {
                    "service": meter_name,
                    "region": region_normalized,
                    "tier": "Standard",
                    "unit_price": 0,
                    "unit": "Hour",
                    "currency": "USD",
                    "note": "Pricing not available from Azure Retail Prices API",
                    "api_source": "Fallback"
                }
                
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching pricing for {service_name}")
        return {
            "service": service_name,
            "region": region,
            "tier": "Standard",
            "unit_price": 0,
            "unit": "Hour",
            "currency": "USD",
            "error": "API timeout",
            "api_source": "Error"
        }
    except Exception as e:
        logger.warning(f"Failed to fetch Azure pricing for {service_name}: {str(e)}")
        return {
            "service": service_name,
            "region": region,
            "tier": "Standard",
            "unit_price": 0,
            "unit": "Hour",
            "currency": "USD",
            "error": str(e),
            "api_source": "Error"
        }


async def estimate_architecture_cost(xml_content: str, config: dict = None) -> dict:
    """
    Analyze DrawIO XML diagram using LLM to intelligently extract services and generate cost estimation.
    
    Approach:
    1. LLM analyzes raw XML to extract services, regions, and architecture patterns
    2. System fetches real-time pricing from Azure Retail Prices API for identified services
    3. LLM performs intelligent cost analysis with actual pricing data
    
    Args:
        xml_content: The DrawIO XML diagram content (direct input from user)
        config: Optional configuration dictionary for pricing calculations
        
    Returns:
        Dictionary with cost breakdown and total estimation
    """
    import aiohttp
    
    # Use provided config or default
    if config is None:
        config = AZURE_PRICING_CONFIG
    
    logger.info("Starting LLM-based cost estimation from XML diagram")
    
    # Load azure_icons for service name mapping
    try:
        icons_path = Path(__file__).parent / "tools" / "azure_icons.json"
        with open(icons_path, 'r', encoding='utf-8') as f:
            azure_icons = json.load(f)
    except Exception as e:
        logger.warning(f"Could not load azure_icons.json: {e}")
        azure_icons = {}
    
    # STEP 1: LLM analyzes XML to extract architecture components
    logger.info("Step 1: LLM analyzing XML to extract services and regions...")
    
    extraction_agent = chat_client.create_agent(
        name="ArchitectureExtractionAgent",
        instructions="""You are an expert at analyzing DrawIO XML diagrams of Azure architectures.

Your task: Extract all Azure services, regions, and architectural patterns from the XML.

Look for:
1. Services: <mxCell> elements with image="img/lib/azure2/.../*.svg"
2. Service names: value="..." attribute in mxCell
3. Regions: <mxCell> elements with id="region*" 
4. Connections: Edge relationships between services
5. Multi-region deployments
6. Service quantities (if multiple instances)

Return JSON with this structure:
{
  "services": [
    {
      "name": "Service display name from XML",
      "icon_path": "img/lib/azure2/category/Service.svg",
      "region": "Region name or 'unknown'",
      "quantity": 1
    }
  ],
  "regions": ["East US", "West Europe"],
  "architecture_patterns": ["multi-region", "load-balanced", "etc"],
  "service_relationships": ["Service A connects to Service B"]
}

Be thorough - extract ALL services visible in the XML.

CRITICAL: Return ONLY valid JSON, nothing else. No explanations, no markdown, just the JSON object."""
    )
    
    extraction_prompt = f"""Analyze this DrawIO XML diagram and extract all Azure services, regions, and architecture details.

**XML Content:**
```xml
{xml_content[:10000]}  <!-- First 10K chars to avoid token limits -->
```

Return ONLY the JSON object with services, regions, patterns, and relationships. No markdown, no explanations."""
    
    try:
        # Add timeout for LLM extraction
        extraction_result = await asyncio.wait_for(
            extraction_agent.run(extraction_prompt),
            timeout=30.0
        )
        # AgentRunResponse has .text attribute, not .content
        response_text = extraction_result.text if hasattr(extraction_result, 'text') else str(extraction_result)
        
        logger.debug(f"Raw LLM response (first 200 chars): {response_text[:200]}")
        
        # Clean response - LLM might wrap JSON in markdown code blocks
        response_text = response_text.strip()
        
        if not response_text:
            raise ValueError("LLM returned empty response")
        
        if response_text.startswith('```json'):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith('```'):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith('```'):
            response_text = response_text[:-3]  # Remove trailing ```
        response_text = response_text.strip()
        
        # Try to find JSON in the response if it's mixed with text
        if '{' in response_text and '}' in response_text:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            response_text = response_text[start_idx:end_idx]
        
        architecture_data = json.loads(response_text)
        logger.info(f"LLM extracted {len(architecture_data.get('services', []))} services from XML")
    except json.JSONDecodeError as e:
        logger.error(f"LLM extraction failed - Invalid JSON: {e}")
        logger.error(f"Response text: {response_text[:500]}")
        # Fallback to regex-based extraction
        return await _fallback_cost_estimation(xml_content, config, azure_icons)
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        logger.error(f"Response text: {response_text[:500] if 'response_text' in locals() else 'No response'}")
        # Fallback to regex-based extraction
        return await _fallback_cost_estimation(xml_content, config, azure_icons)
    
    # STEP 2: Fetch real-time pricing from Azure API for each extracted service
    logger.info("Step 2: Fetching real-time pricing from Azure Retail Prices API...")
    pricing_data = []
    
    for service in architecture_data.get('services', []):
        service_name = service.get('name', '')
        icon_path = service.get('icon_path', '')
        region = service.get('region', 'eastus').lower().replace(' ', '')
        quantity = service.get('quantity', 1)
        
        if not service_name:
            continue
        
        # Infer service name and category from icon path
        inferred_name, category = infer_service_name_from_icon_path(icon_path, azure_icons)
        
        # Use LLM to resolve to Azure Pricing API service name
        service_type = await resolve_azure_pricing_service_name(inferred_name, category)
        
        # Check if this is a global service and override region
        global_service_keywords = ['front door', 'traffic manager', 'cdn']
        if any(keyword in service_type.lower() for keyword in global_service_keywords):
            region = 'global'  # Use 'global' as indicator for global services
        
        # Fetch pricing with multiple SKU options
        pricing = await get_azure_pricing(service_type, region, include_multiple_skus=True, config=config)
        pricing_data.append({
            "name": service_name,
            "type": service_type,
            "region": region,
            "quantity": quantity,
            "pricing": pricing
        })
    
    logger.info(f"Retrieved pricing data from Azure Retail Prices API for {len(pricing_data)} services")
    
    # Build analysis prompt with real pricing data
    region_list = "\n".join([f"- {region}" for region in architecture_data.get('regions', ['Single Region'])])
    architecture_patterns = "\n".join([f"- {pattern}" for pattern in architecture_data.get('architecture_patterns', [])])
    
    # Format pricing data from Azure Retail Prices API for AI analysis
    pricing_summary = []
    services_with_real_pricing = 0
    
    for item in pricing_data:
        pricing_info = item['pricing']
        service_display = f"**{item['name']}** ({item['type']}) in {item['region'].upper()}"
        
        # Check if we have real API data or error/fallback
        if 'error' in pricing_info:
            pricing_summary.append(f"- {service_display}: ⚠️ API Error - {pricing_info['error']}")
            continue
        
        if 'pricing_options' in pricing_info and pricing_info['pricing_options']:
            # Multiple SKU tiers available
            services_with_real_pricing += 1
            pricing_summary.append(f"- {service_display}:")
            pricing_summary.append(f"  ✓ Source: {pricing_info.get('api_source', 'Azure Retail Prices API')}")
            pricing_summary.append(f"  Available SKU Tiers:")
            
            for sku in pricing_info['pricing_options']:
                sku_name = sku.get('sku_name', 'Standard')
                unit_price = sku.get('unit_price', 0)
                unit = sku.get('unit', 'Hour')
                monthly = calculate_monthly_cost(unit_price, unit, config)
                pricing_summary.append(f"    • {sku_name}: ${unit_price:.4f}/{unit} → ${monthly:.2f}/month")
                if 'meter_name' in sku:
                    pricing_summary.append(f"      Meter: {sku['meter_name']}")
        elif pricing_info.get('unit_price', 0) > 0:
            # Single pricing tier
            services_with_real_pricing += 1
            unit_price = pricing_info['unit_price']
            unit = pricing_info['unit']
            monthly_cost = calculate_monthly_cost(unit_price, unit, config)
            tier = pricing_info.get('tier_name', 'Standard')
            pricing_summary.append(
                f"- {service_display}: ${unit_price:.4f}/{unit} "
                f"({tier} tier) → ${monthly_cost:.2f}/month"
            )
            pricing_summary.append(f"  ✓ Source: {pricing_info.get('api_source', 'Azure Retail Prices API')}")
        else:
            pricing_summary.append(f"- {service_display}: Pricing not available - use typical estimates")
    
    pricing_details = "\n".join(pricing_summary)
    logger.info(f"Real Azure pricing data available for {services_with_real_pricing}/{len(pricing_data)} services")
    
    cost_prompt = f"""Analyze this Azure architecture and provide DETAILED cost estimation using the REAL pricing data from Azure Retail Prices API.

**ARCHITECTURE ANALYSIS (from LLM extraction of XML):**
Regions:
{region_list}

Patterns Detected:
{architecture_patterns if architecture_patterns else "- Standard single-region deployment"}

**REAL-TIME PRICING FROM AZURE API:**
{pricing_details}

**YOUR TASK:**
1. **Use ACTUAL Azure Retail Prices API data** - The pricing above is from the official Azure Retail Prices API ({config['api_base_url']})
2. **Choose appropriate SKU tier** - When multiple tiers are listed (Basic, Standard, Premium), select based on production requirements:
   - Production workloads: Standard or Premium
   - Dev/Test: Basic or Standard
   - High availability: Premium
3. **Use exact API prices** - Do NOT estimate or guess when real pricing is provided with ✓ checkmark
4. **Monthly calculations** - Already converted using standard calculation ({config.get('hours_per_month', 730)} hours/month for hourly services)
5. **Multi-region costs** - If architecture spans multiple regions, multiply service costs by number of regions
6. **Data transfer costs** (use these rates):
   - Inter-region transfer: ${config['data_transfer_costs']['inter_region_per_gb']:.3f}/GB
   - Egress to internet: ${config['data_transfer_costs']['egress_internet_per_gb']:.3f}/GB (first 10TB)
   - Intra-region: ${config['data_transfer_costs']['intra_region_per_gb']:.3f}/GB
7. **Usage assumptions** - State realistic production usage:
   - Storage: XX GB/TB
   - Requests: XX million/month
   - Bandwidth: XX GB/month
8. **Include hidden costs**:
   - Backup/disaster recovery
   - Monitoring (Application Insights, Log Analytics)
   - Security (Key Vault transactions, etc.)

**OUTPUT FORMAT (JSON):**
```json
{{
  "assumptions": ["List key assumptions made for estimation"],
  "services": [
    {{
      "name": "Service Name",
      "type": "Azure Service Type",
      "tier": "Selected Tier",
      "quantity": "1x per region or total count",
      "unit_cost": 100.00,
      "total_cost": 100.00,
      "notes": "Any relevant notes"
    }}
  ],
  "regions": [
    {{
      "name": "Region Name",
      "monthly_cost": 500.00
    }}
  ],
  "data_transfer": {{
    "inter_region": 50.00,
    "egress": 25.00
  }},
  "monthly_total": 1500.00,
  "annual_total": 18000.00,
  "breakdown_by_category": {{
    "compute": 600.00,
    "storage": 200.00,
    "networking": 100.00,
    "data": 300.00,
    "ai_ml": 200.00,
    "security": 100.00
  }}
}}
```

Be realistic and conservative with estimates. Use current Azure pricing (2024-2025)."""

    try:
        # Create cost estimation agent
        cost_agent = chat_client.create_agent(
            name="CostEstimationAgent",
            instructions="""You are an Azure cost estimation expert. You analyze Azure architecture diagrams and provide detailed, accurate cost estimates.

Your expertise includes:
- Current Azure service pricing across all tiers
- Multi-region cost implications
- Data transfer and egress costs
- Hidden costs (backups, monitoring, etc.)
- Cost optimization recommendations

Always provide:
1. Detailed service-level breakdown
2. Realistic tier selections based on production workloads
3. Monthly and annual projections
4. Clear assumptions
5. Category-wise cost grouping

Output ONLY valid JSON as specified in the prompt.""",
            tools=[]
        )
        
        result = await asyncio.wait_for(cost_agent.run(cost_prompt), timeout=60.0)
        response_text = result.text if hasattr(result, 'text') else str(result)
        
        logger.info(f"Cost estimation response received ({len(response_text)} chars)")
        
        # Clean JSON if wrapped
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        cost_data = json.loads(response_text)
        
        logger.info(f"Cost estimation complete: ${cost_data.get('monthly_total', 0):.2f}/month")
        
        return {
            "status": "success",
            "estimation": cost_data
        }
        
    except asyncio.TimeoutError:
        logger.error("Cost estimation timed out")
        return {
            "status": "error",
            "message": "Cost estimation timed out. Please try again."
        }
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from cost agent: {e}")
        return {
            "status": "error",
            "message": "Failed to parse cost estimation. Please try again."
        }
    except Exception as e:
        logger.error(f"Cost estimation error: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Cost estimation failed: {str(e)}"
        }
