# Hello Agent - Microsoft Agent Framework Demo

This project demonstrates how to create a simple agent using the official Microsoft Agent Framework SDK with Azure OpenAI that can respond to prompts and use basic tools like a calculator and summarizer.

## Setup Instructions

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Azure OpenAI**:
   - Copy `.env.example` to `.env`
   - Update the `.env` file with your Azure OpenAI resource details:
     ```
     AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
     AZURE_OPENAI_API_KEY=your_api_key_here
     AZURE_OPENAI_API_VERSION=2024-02-15-preview
     AZURE_OPENAI_DEPLOYMENT=gpt-4
     ```

3. **Run the Notebook**:
   ```bash
   jupyter notebook hello_agent.ipynb
   ```

## Azure OpenAI Setup

To use this demo, you'll need:

1. **Azure OpenAI Resource**: Create an Azure OpenAI resource in the Azure portal
2. **Model Deployment**: Deploy a model (GPT-4 recommended) in your Azure OpenAI resource
3. **API Keys**: Copy the endpoint and API key from your Azure OpenAI resource
4. **Configuration**: Update the `.env` file with your specific values

### Getting Azure OpenAI Credentials

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Azure OpenAI resource
3. Go to "Keys and Endpoint" section
4. Copy the endpoint URL and one of the keys
5. Note your deployment name from the "Model deployments" section

## What's Included

- **hello_agent.ipynb**: Main notebook with complete demonstration
- **requirements.txt**: All necessary Python dependencies  
- **README.md**: This setup guide
- **.env.example**: Template for environment configuration
- **.gitignore**: Excludes sensitive files from version control

## Features Demonstrated

- ✅ Microsoft Agent Framework SDK setup with Azure OpenAI
- ✅ Function calling with Azure OpenAI models
- ✅ Custom tool creation (Calculator and Summarizer)
- ✅ Agent initialization with tool registry
- ✅ Conversational interactions
- ✅ Automatic tool selection and usage via function calling
- ✅ Complex multi-tool scenarios
- ✅ Interactive demo mode with fallback for no Azure OpenAI

## Tools Included

1. **Calculator Tool**: Performs basic arithmetic operations using function calling
2. **Summarizer Tool**: Provides text summarization capabilities using function calling

## Usage Examples

```python
# Calculator usage
"Can you calculate 15 + 25?"
"What's 144 / 12?"

# Summarizer usage
'Please summarize this: "Your text here..."'

# Conversational
"Hello! What can you do?"
"Tell me about yourself"
```

## Microsoft Agent Framework SDK

This demo uses the official Microsoft Agent Framework SDK, which provides:
- Integration with Azure OpenAI and other LLM providers
- Advanced function calling capabilities
- Tool registry and management
- Conversation management and memory
- Enterprise-ready security and compliance

For more information, visit: https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview

---

**Happy coding with the Microsoft Agent Framework!** 