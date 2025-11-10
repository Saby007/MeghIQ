# Microsoft Agent Framework - Project Collection

A collection of AI agent projects built with Microsoft Agent Framework and Azure OpenAI, demonstrating various use cases from simple chat agents to complex multi-agent business intelligence systems.

## 📁 Projects Overview

### 1. HelloAgent
A simple introduction to Microsoft Agent Framework, demonstrating basic agent creation and Azure OpenAI integration.

**Key Features:**
- Basic chat agent implementation
- Azure OpenAI GPT-4 integration
- Environment configuration setup
- Interactive console interface

**Use Case:** Perfect for learning Agent Framework basics and testing Azure OpenAI connectivity.

### 2. MultiAgentDB - Business Intelligence System
An advanced multi-agent system for business intelligence and data analysis, showcasing coordinated AI agents working together.

**Key Features:**
- 4 specialized AI agents (Customer, Sales, Product, BI Coordinator)
- Sequential orchestration patterns
- Business data analysis with pandas DataFrames
- Interactive Jupyter notebook interface
- Multi-agent collaborative workflows

**Use Case:** Demonstrates enterprise-grade multi-agent architectures for business analytics.

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+**
- **Azure OpenAI Resource** with GPT-4 deployment
- **Azure CLI** for authentication
- **Git** for version control

### Global Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Project
   ```

2. **Set up Azure CLI authentication**
   ```bash
   az login
   ```

3. **Choose your project:**
   - For basic agent concepts → `cd HelloAgent`
   - For multi-agent systems → `cd MultiAgentDB`

### Environment Configuration

Both projects require Azure OpenAI configuration. Create a `.env` file in each project directory:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-01
```

## 📋 Project Details

### HelloAgent
```
HelloAgent/
├── hello_agent_console.py    # Console-based agent demo
├── hello_agent.ipynb         # Jupyter notebook version
├── README.md                 # Project documentation
└── requirements.txt          # Python dependencies
```

**Run HelloAgent:**
```bash
cd HelloAgent
pip install -r requirements.txt
python hello_agent_console.py
```

### MultiAgentDB - Business Intelligence
```
MultiAgentDB/
├── multi_agent_azure_openai.py     # Main console application
├── multi_agent_bi_notebook.ipynb   # Interactive Jupyter notebook
├── .env.example                    # Environment template
├── README.md                       # Detailed project docs
└── requirements.txt                # Python dependencies
```

**Run MultiAgentDB:**
```bash
cd MultiAgentDB
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Azure OpenAI details
python multi_agent_azure_openai.py
```

**Or use Jupyter notebook:**
```bash
jupyter notebook multi_agent_bi_notebook.ipynb
```

## 🏗️ Architecture Patterns

### Single Agent Pattern (HelloAgent)
- Direct client-agent interaction
- Simple request-response flow
- Basic Azure OpenAI integration

### Multi-Agent Orchestration (MultiAgentDB)
- Specialized agent roles
- Sequential workflow coordination
- Data-driven business intelligence
- Interactive multi-agent communication

## 🔧 Technical Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **AI Framework** | Microsoft Agent Framework | Agent creation and management |
| **LLM Service** | Azure OpenAI GPT-4 | Natural language processing |
| **Authentication** | Azure Identity | Secure Azure service access |
| **Data Processing** | Pandas | Business data analysis |
| **Environment** | Python 3.8+ | Runtime environment |
| **Notebooks** | Jupyter | Interactive development |

## 📊 Use Cases Demonstrated

### Business Intelligence
- Customer segmentation analysis
- Sales performance tracking
- Product portfolio optimization
- Executive reporting automation

### Agent Coordination
- Sequential workflow orchestration
- Specialized agent roles
- Multi-agent collaboration patterns
- Interactive agent communication

### Integration Patterns
- Azure OpenAI service integration
- Environment-based configuration
- Pandas data source integration
- Jupyter notebook compatibility

## 🔒 Security & Configuration

### Azure Authentication
Both projects use Azure CLI authentication with `DefaultAzureCredential`:
- No API keys stored in code
- Leverages Azure AD authentication
- Supports managed identity in cloud deployments

### Environment Management
- Sensitive configuration in `.env` files
- Template files (`.env.example`) for easy setup
- Environment validation and error handling

## 📈 Getting Started Recommendations

### For Beginners
1. **Start with HelloAgent** to understand basic concepts
2. **Configure Azure OpenAI** and test connectivity
3. **Explore interactive features** in the console application
4. **Try the Jupyter notebook** for step-by-step learning

### For Advanced Users
1. **Jump to MultiAgentDB** for complex scenarios
2. **Examine agent coordination patterns** in the workflow
3. **Experiment with custom agents** and specialized tools
4. **Explore business data integration** possibilities

## 🛠️ Development Guidelines

### Adding New Agents
1. Define specialized instructions and capabilities
2. Create focused tool functions for agent tasks
3. Implement proper error handling and validation
4. Add interactive demonstrations and tests

### Extending Functionality
1. Add new business analysis functions
2. Create additional specialized agents
3. Implement advanced orchestration patterns
4. Integrate with external data sources

## 📝 Documentation

Each project includes comprehensive documentation:
- **README.md** - Setup and usage instructions
- **Inline comments** - Code documentation
- **Jupyter notebooks** - Interactive tutorials
- **Requirements files** - Dependency management

## 🤝 Contributing

When contributing to these projects:
1. Follow existing code organization patterns
2. Maintain clean, professional code style
3. Include proper error handling and validation
4. Add documentation for new features
5. Test with different Azure OpenAI configurations

## 📞 Support

For issues or questions:
1. Check project-specific README files
2. Verify Azure OpenAI configuration
3. Ensure proper Azure CLI authentication
4. Review error messages and logs

## 🔮 Future Enhancements

### Potential Additions
- **Real database integration** (SQL Server, Cosmos DB)
- **Advanced visualization dashboards** (Plotly, Streamlit)
- **Streaming data processing** capabilities
- **Multi-tenant agent architectures**
- **Custom orchestration patterns**
- **API-based agent interfaces**

---

**Built with Microsoft Agent Framework and Azure OpenAI**  
*Demonstrating the future of enterprise AI agent systems*