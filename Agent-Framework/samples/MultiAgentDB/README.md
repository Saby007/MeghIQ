# Multi-Agent Business Intelligence System

A multi-agent business intelligence system built with Microsoft Agent Framework and Azure OpenAI. This application demonstrates how to create specialized AI agents that work together to provide comprehensive business analysis.

## Features

- **Customer Analysis Agent**: Analyzes customer segmentation, portfolio value, and trends
- **Sales Analysis Agent**: Provides sales performance insights across different time periods  
- **Product Analysis Agent**: Delivers product performance analytics and recommendations
- **Business Intelligence Coordinator**: Generates executive reports and coordinates multi-agent workflows

## Prerequisites

- Python 3.8 or higher
- Azure OpenAI resource with GPT-4 deployment
- Azure CLI for authentication

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Azure OpenAI**
   
   Copy the environment template:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your Azure OpenAI details:
   ```
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4
   AZURE_OPENAI_API_VERSION=2024-02-01
   ```

3. **Authenticate with Azure**
   ```bash
   az login
   ```

## Usage

Run the multi-agent system:
```bash
python multi_agent_azure_openai.py
```

The application will:
1. Initialize business data (customers, orders, products)
2. Create four specialized AI agents
3. Run capability demonstrations for each agent
4. Execute a multi-agent collaborative workflow
5. Start an interactive session for real-time analysis

## Interactive Commands

- `agent1`, `agent2`, `agent3`, `agent4` - Switch between agents
- `workflow` - Run complete multi-agent analysis
- `quit`, `exit`, `bye` - End session

## Agent Capabilities

### CustomerAnalyst
- Customer segmentation analysis
- Portfolio value assessment
- Regional distribution insights
- Customer retention recommendations

### SalesAnalyst  
- Revenue trend analysis
- Monthly/quarterly performance metrics
- Sales forecasting insights
- Performance benchmarking

### ProductAnalyst
- Product performance evaluation
- Sales volume analysis
- Pricing optimization recommendations
- Product portfolio insights

### BICoordinator
- Executive summary generation
- Cross-functional analysis coordination
- Strategic recommendations
- KPI reporting

## Architecture

The system uses Microsoft Agent Framework with Azure OpenAI to create intelligent agents that can:
- Process business data using pandas
- Generate insights through AI-powered analysis
- Coordinate workflows between specialized agents
- Provide interactive business intelligence capabilities

## Data Model

The application uses sample business data including:
- **Customers**: 5 sample customers across different segments and regions
- **Orders**: 8 sample orders with product and pricing information
- **Products**: 3 sample products (Analytics Platform, AI Assistant, Data Pipeline)

## Requirements

See `requirements.txt` for complete dependency list. Key dependencies include:
- `agent-framework` - Microsoft Agent Framework
- `openai` - Azure OpenAI client
- `azure-identity` - Azure authentication
- `pandas` - Data processing
- `python-dotenv` - Environment configuration

## License

This project is for demonstration purposes.