"""
Multi-Agent Business Intelligence Console Application
Microsoft Agent Framework with Azure OpenAI Integration

Console application demonstrating multi-agent business intelligence workflows
using the Microsoft Agent Framework with Azure OpenAI integration.
"""

import os
import asyncio
import pandas as pd
from typing import Annotated, List, Dict, Any
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from pydantic import Field
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


class BusinessDataManager:
    """Manages business data using pandas DataFrames."""
    
    def __init__(self):
        """Initialize with sample business data."""
        # Sample customer data
        self.customers_df = pd.DataFrame({
            'customer_id': [1, 2, 3, 4, 5],
            'name': ['Acme Corp', 'TechStart Inc', 'Global Solutions', 'InnovateCo', 'DataDriven Ltd'],
            'segment': ['Enterprise', 'SMB', 'Enterprise', 'SMB', 'Mid-Market'],
            'region': ['North', 'South', 'East', 'West', 'North'],
            'total_value': [150000, 45000, 200000, 35000, 85000]
        })
        
        # Sample orders data
        self.orders_df = pd.DataFrame({
            'order_id': [101, 102, 103, 104, 105, 106, 107, 108],
            'customer_id': [1, 2, 1, 3, 4, 2, 3, 5],
            'product_id': [201, 202, 203, 201, 202, 203, 201, 202],
            'quantity': [5, 2, 3, 8, 1, 4, 6, 3],
            'unit_price': [1000, 2500, 1500, 1000, 2500, 1500, 1000, 2500],
            'order_date': pd.to_datetime(['2024-01-15', '2024-01-18', '2024-01-20', 
                                        '2024-02-01', '2024-02-05', '2024-02-10', 
                                        '2024-02-15', '2024-02-20'])
        })
        
        # Sample products data
        self.products_df = pd.DataFrame({
            'product_id': [201, 202, 203],
            'product_name': ['Analytics Platform', 'AI Assistant', 'Data Pipeline'],
            'category': ['Software', 'AI/ML', 'Data'],
            'base_price': [1000, 2500, 1500]
        })
        
        print("Business data initialized successfully!")
        print(f"Loaded {len(self.customers_df)} customers, {len(self.orders_df)} orders, {len(self.products_df)} products")


# Agent Tool Functions
def get_customer_summary(
    data_manager: BusinessDataManager = None
) -> str:
    """Get summary of customer data."""
    if data_manager is None:
        return "Data manager not available"
    
    df = data_manager.customers_df
    total_customers = len(df)
    total_value = df['total_value'].sum()
    avg_value = df['total_value'].mean()
    
    segment_breakdown = df['segment'].value_counts().to_dict()
    region_breakdown = df['region'].value_counts().to_dict()
    
    return f"""Customer Analysis Summary:
Total Customers: {total_customers}
Total Portfolio Value: ${total_value:,}
Average Customer Value: ${avg_value:,.0f}
Segment Distribution: {segment_breakdown}
Region Distribution: {region_breakdown}"""


def analyze_sales_performance(
    data_manager: BusinessDataManager = None,
    period: Annotated[str, Field(description="Time period: 'monthly', 'quarterly', or 'all'")] = "all"
) -> str:
    """Analyze sales performance by period."""
    if data_manager is None:
        return "Data manager not available"
    
    # Merge orders with customer and product data
    orders = data_manager.orders_df.copy()
    orders['total_amount'] = orders['quantity'] * orders['unit_price']
    orders['month'] = orders['order_date'].dt.strftime('%Y-%m')
    
    if period == "monthly":
        monthly_sales = orders.groupby('month')['total_amount'].sum()
        return f"Monthly Sales Performance:\n{monthly_sales.to_string()}"
    elif period == "quarterly":
        orders['quarter'] = orders['order_date'].dt.quarter
        quarterly_sales = orders.groupby('quarter')['total_amount'].sum()
        return f"Quarterly Sales Performance:\n{quarterly_sales.to_string()}"
    else:
        total_revenue = orders['total_amount'].sum()
        avg_order_value = orders['total_amount'].mean()
        total_orders = len(orders)
        return f"""Overall Sales Performance:
Total Revenue: ${total_revenue:,}
Total Orders: {total_orders}
Average Order Value: ${avg_order_value:,.0f}"""


def get_product_insights(
    data_manager: BusinessDataManager = None
) -> str:
    """Get insights about product performance."""
    if data_manager is None:
        return "Data manager not available"
    
    # Merge orders with products
    orders = data_manager.orders_df.copy()
    products = data_manager.products_df.copy()
    
    merged = orders.merge(products, on='product_id')
    merged['total_amount'] = merged['quantity'] * merged['unit_price']
    
    product_performance = merged.groupby('product_name').agg({
        'total_amount': 'sum',
        'quantity': 'sum',
        'order_id': 'count'
    }).round(2)
    
    return f"""Product Performance Analysis:
{product_performance.to_string()}

Top Selling Product: {product_performance['total_amount'].idxmax()}
Most Ordered Product: {product_performance['quantity'].idxmax()}"""


def generate_business_report(
    data_manager: BusinessDataManager = None,
    report_type: Annotated[str, Field(description="Report type: 'executive', 'detailed', or 'kpi'")] = "executive"
) -> str:
    """Generate comprehensive business report."""
    if data_manager is None:
        return "Data manager not available"
    
    # Calculate key metrics
    customers = data_manager.customers_df
    orders = data_manager.orders_df.copy()
    orders['total_amount'] = orders['quantity'] * orders['unit_price']
    
    total_customers = len(customers)
    total_revenue = orders['total_amount'].sum()
    total_orders = len(orders)
    
    if report_type == "executive":
        return f"""EXECUTIVE BUSINESS REPORT
========================
Key Performance Indicators:
Customer Base: {total_customers} active customers
Total Revenue: ${total_revenue:,}
Order Volume: {total_orders} orders processed
Revenue per Customer: ${total_revenue/total_customers:,.0f}

Business Highlights:
Top Customer Segment: {customers['segment'].value_counts().index[0]}
Primary Region: {customers['region'].value_counts().index[0]}
Average Order Value: ${orders['total_amount'].mean():,.0f}"""
    
    elif report_type == "kpi":
        return f"""KEY PERFORMANCE INDICATORS
=========================
Customer Metrics:
• Total Customers: {total_customers}
• Customer Portfolio Value: ${customers['total_value'].sum():,}

Sales Metrics:
• Total Revenue: ${total_revenue:,}
• Total Orders: {total_orders}
• Average Order Value: ${orders['total_amount'].mean():,.0f}
• Revenue Growth Rate: Calculated from order trends"""
    
    else:  # detailed
        monthly_trend = orders.groupby(orders['order_date'].dt.strftime('%Y-%m'))['total_amount'].sum()
        return f"""DETAILED BUSINESS REPORT
=======================
Customer Analysis: {get_customer_summary(data_manager)}

Sales Analysis: {analyze_sales_performance(data_manager)}

Product Analysis: {get_product_insights(data_manager)}

Monthly Revenue Trend:
{monthly_trend.to_string()}"""


def setup_environment():
    """Setup and validate environment variables."""
    load_dotenv()
    
    print("Multi-Agent Business Intelligence - Microsoft Agent Framework Demo")
    print("=" * 70)
    print("Checking Azure OpenAI configuration...")
    
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    deployment_name = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION')
    
    print(f"AZURE_OPENAI_ENDPOINT: {'OK' if endpoint else 'MISSING'}")
    print(f"AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: {'OK' if deployment_name else 'MISSING'}")
    print(f"AZURE_OPENAI_API_VERSION: {'OK' if api_version else 'MISSING'}")
    
    if not all([endpoint, deployment_name, api_version]):
        print("\nError: Missing required environment variables!")
        print("Please create a .env file with:")
        print("AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
        print("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=your-chat-deployment-name")
        print("AZURE_OPENAI_API_VERSION=2024-02-01")
        print("\nThen authenticate with: az login")
        return None
    
    return endpoint, deployment_name, api_version


def create_azure_client(endpoint, deployment_name, api_version):
    """Create and return Azure OpenAI client."""
    try:
        client = AzureOpenAIChatClient(
            endpoint=endpoint,
            deployment_name=deployment_name,
            api_version=api_version,
            credential=DefaultAzureCredential()
        )
        print("Azure OpenAI client created successfully!")
        return client
    except Exception as e:
        print(f"Error creating Azure OpenAI client: {e}")
        print("Make sure you're authenticated with 'az login'")
        return None


def create_agents(client, data_manager):
    """Create specialized business intelligence agents."""
    
    # Create closure functions that have access to data_manager
    def customer_summary_tool() -> str:
        return get_customer_summary(data_manager)
    
    def sales_analysis_tool(period: Annotated[str, Field(description="Time period: 'monthly', 'quarterly', or 'all'")] = "all") -> str:
        return analyze_sales_performance(data_manager, period)
    
    def product_insights_tool() -> str:
        return get_product_insights(data_manager)
    
    def business_report_tool(report_type: Annotated[str, Field(description="Report type: 'executive', 'detailed', or 'kpi'")] = "executive") -> str:
        return generate_business_report(data_manager, report_type)
    
    # Customer Analysis Agent
    customer_agent = ChatAgent(
        chat_client=client,
        name="CustomerAnalyst",
        instructions="""You are a Customer Analysis Specialist. You excel at:
- Analyzing customer data and segmentation
- Identifying customer trends and patterns
- Providing customer insights and recommendations
- Understanding customer portfolio value and distribution

Use the customer_summary_tool to get detailed customer analysis.""",
        tools=[customer_summary_tool]
    )
    
    # Sales Analysis Agent  
    sales_agent = ChatAgent(
        chat_client=client,
        name="SalesAnalyst", 
        instructions="""You are a Sales Performance Analyst. You specialize in:
- Analyzing sales performance across different time periods
- Identifying sales trends and patterns
- Calculating revenue metrics and KPIs
- Providing sales insights and forecasts

Use the sales_analysis_tool to analyze performance by period (monthly, quarterly, or all).""",
        tools=[sales_analysis_tool]
    )
    
    # Product Analysis Agent
    product_agent = ChatAgent(
        chat_client=client,
        name="ProductAnalyst",
        instructions="""You are a Product Performance Analyst. You focus on:
- Analyzing product sales performance
- Understanding product popularity and trends
- Identifying top-performing products
- Providing product strategy recommendations

Use the product_insights_tool to get comprehensive product analysis.""",
        tools=[product_insights_tool]
    )
    
    # Business Intelligence Coordinator
    coordinator_agent = ChatAgent(
        chat_client=client,
        name="BICoordinator",
        instructions="""You are the Business Intelligence Coordinator. You orchestrate comprehensive analysis by:
- Coordinating between different analysis specialists
- Generating executive and detailed business reports
- Synthesizing insights from multiple data sources
- Providing strategic business recommendations

Use the business_report_tool to generate different types of reports (executive, detailed, kpi).""",
        tools=[business_report_tool]
    )
    
    agents = {
        'customer': customer_agent,
        'sales': sales_agent, 
        'product': product_agent,
        'coordinator': coordinator_agent
    }
    
    print(f"\nCreated 4 specialized BI agents:")
    for name, agent in agents.items():
        print(f"  - {agent.name}: {name} analysis specialist")
    
    return agents


async def run_agent_demonstrations(agents):
    """Run demonstrations of each agent's capabilities."""
    print("\n" + "=" * 50)
    print("AGENT CAPABILITY DEMONSTRATIONS")
    print("=" * 50)
    
    # Customer Agent Demo
    print("\nCustomer Analysis Agent Demo:")
    print("-" * 30)
    response = await agents['customer'].run("Please provide a comprehensive customer analysis")
    print(f"CustomerAnalyst: {response.text}")
    
    # Sales Agent Demo
    print("\nSales Analysis Agent Demo:")
    print("-" * 25)
    response = await agents['sales'].run("Show me monthly sales performance analysis")
    print(f"SalesAnalyst: {response.text}")
    
    # Product Agent Demo  
    print("\nProduct Analysis Agent Demo:")
    print("-" * 27)
    response = await agents['product'].run("Analyze our product performance and identify top sellers")
    print(f"ProductAnalyst: {response.text}")
    
    # Coordinator Agent Demo
    print("\nBusiness Intelligence Coordinator Demo:")
    print("-" * 38)
    response = await agents['coordinator'].run("Generate an executive business report with key insights")
    print(f"BICoordinator: {response.text}")


async def run_multi_agent_workflow(agents):
    """Demonstrate multi-agent workflow for comprehensive business analysis."""
    print("\n" + "=" * 60)
    print("MULTI-AGENT COLLABORATIVE WORKFLOW")
    print("=" * 60)
    
    workflow_steps = [
        ("Customer Analysis", agents['customer'], "Analyze our customer base, segmentation, and portfolio value"),
        ("Sales Performance", agents['sales'], "Analyze sales performance for all time periods"), 
        ("Product Insights", agents['product'], "Provide insights on product performance and top sellers"),
        ("Executive Summary", agents['coordinator'], "Create an executive report combining all insights")
    ]
    
    results = []
    
    for step_name, agent, prompt in workflow_steps:
        print(f"\nStep: {step_name}")
        print(f"Agent: {agent.name}")
        print(f"Task: {prompt}")
        print("-" * 50)
        
        try:
            response = await agent.run(prompt)
            print(f"Completed - {agent.name}: {response.text[:200]}...")
            results.append(f"{step_name}: {response.text}")
        except Exception as e:
            print(f"Error in {step_name}: {e}")
            results.append(f"{step_name}: Error occurred")
    
    print(f"\nMulti-agent workflow completed! Generated {len(results)} analysis reports.")
    return results


async def interactive_multi_agent_chat(agents):
    """Interactive chat with agent selection and routing."""
    print("\n" + "=" * 60)
    print("INTERACTIVE MULTI-AGENT BUSINESS INTELLIGENCE")
    print("=" * 60)
    print("Available agents:")
    print("  1. CustomerAnalyst - Customer analysis and segmentation")
    print("  2. SalesAnalyst - Sales performance and trends")
    print("  3. ProductAnalyst - Product performance insights")
    print("  4. BICoordinator - Executive reports and strategy")
    print("\nCommands:")
    print("  'agent1', 'agent2', 'agent3', 'agent4' - Switch agents")
    print("  'workflow' - Run complete multi-agent analysis")
    print("  'quit', 'exit', 'bye' - End session")
    print()
    
    current_agent_key = 'coordinator'
    current_agent = agents[current_agent_key]
    
    while True:
        try:
            print(f"\n[Current: {current_agent.name}]")
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Thank you for using Multi-Agent Business Intelligence!")
                break
            
            if not user_input:
                continue
            
            # Agent switching commands
            agent_map = {'agent1': 'customer', 'agent2': 'sales', 'agent3': 'product', 'agent4': 'coordinator'}
            if user_input.lower() in agent_map:
                current_agent_key = agent_map[user_input.lower()]
                current_agent = agents[current_agent_key]
                print(f"Switched to {current_agent.name}")
                continue
            
            # Multi-agent workflow command
            if user_input.lower() == 'workflow':
                print("Starting multi-agent workflow...")
                await run_multi_agent_workflow(agents)
                continue
            
            # Regular agent interaction
            print(f"{current_agent.name}: ", end="", flush=True)
            response = await current_agent.run(user_input)
            print(response.text)
            
        except KeyboardInterrupt:
            print("\nChat session interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Main application entry point."""
    # Setup environment
    env_config = setup_environment()
    if not env_config:
        return
    
    endpoint, deployment_name, api_version = env_config
    
    # Create Azure client
    client = create_azure_client(endpoint, deployment_name, api_version)
    if not client:
        return
    
    # Initialize business data
    data_manager = BusinessDataManager()
    
    # Create specialized agents
    agents = create_agents(client, data_manager)
    
    # Run demonstrations
    await run_agent_demonstrations(agents)
    
    # Run multi-agent workflow
    await run_multi_agent_workflow(agents)
    
    # Interactive session
    await interactive_multi_agent_chat(agents)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication interrupted. Goodbye!")
    except Exception as e:
        print(f"Application error: {e}")