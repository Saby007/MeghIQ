"""
Hello Agent Console Application
Microsoft Agent Framework Demo

A simple console application demonstrating the Microsoft Agent Framework
with Azure OpenAI integration and basic tools (calculator and summarizer).
"""

import os
import asyncio
from typing import Annotated
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from pydantic import Field
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


def calculator(
    expression: Annotated[str, Field(description="Math expression like '2+2' or '10*5'")]
) -> str:
    """Calculate mathematical expressions."""
    try:
        # Safety check - only allow basic math
        allowed = set('0123456789+-*/.() ')
        if not all(c in allowed for c in expression):
            return "Error: Only basic math operations allowed"
        
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {str(e)}"


def summarizer(
    text: Annotated[str, Field(description="Text to summarize")]
) -> str:
    """Summarize text by taking key sentences."""
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    if len(sentences) <= 2:
        return text
    return f"{sentences[0]}. {sentences[-1]}."


def setup_environment():
    """Setup and validate environment variables."""
    load_dotenv()
    
    print("Hello Agent - Microsoft Agent Framework Demo")
    print("=" * 50)
    print("Checking environment configuration...")
    
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


def test_tools():
    """Test the agent tools independently."""
    print("\n" + "=" * 30)
    print("Testing Agent Tools")
    print("=" * 30)
    
    print("Calculator:", calculator("2 + 3 * 4"))
    print("Summarizer:", summarizer("This is a test. It has multiple sentences. This is the end."))


def create_agent(client):
    """Create and return the HelloAgent instance."""
    agent = ChatAgent(
        chat_client=client,
        name="HelloAgent",
        instructions="""You are HelloAgent, a friendly AI assistant. 

You have two tools:
- Calculator: for math expressions
- Summarizer: for summarizing text

Be helpful and use tools when appropriate.""",
        tools=[calculator, summarizer]
    )
    
    print(f"\nHelloAgent created with 2 tools!")
    print(f"Agent name: {agent.name}")
    return agent


async def run_basic_tests(agent):
    """Run basic conversation tests."""
    print("\n" + "=" * 30)
    print("Basic Chat Test")
    print("=" * 30)
    
    test_cases = [
        "Hello! What's your name?",
        "What tools do you have available?"
    ]
    
    for prompt in test_cases:
        print(f"\nUser: {prompt}")
        try:
            response = await agent.run(prompt)
            print(f"HelloAgent: {response}")
        except Exception as e:
            print(f"Error: {e}")


async def run_tool_tests(agent):
    """Run tool usage tests."""
    print("\n" + "=" * 30)
    print("Tool Usage Test")
    print("=" * 30)
    
    test_cases = [
        "Calculate 25 + 17",
        "What's 144 divided by 12?",
        "Please summarize: The Microsoft Agent Framework is a powerful SDK for building AI agents. It provides simple APIs for creating conversational AI applications. The framework integrates with Azure OpenAI and supports function calling for tool usage."
    ]
    
    for i, prompt in enumerate(test_cases, 1):
        print(f"\n--- Test {i} ---")
        print(f"User: {prompt}")
        try:
            response = await agent.run(prompt)
            print(f"HelloAgent: {response}")
        except Exception as e:
            print(f"Error: {e}")


async def interactive_chat(agent):
    """Start an interactive chat session with the agent."""
    print("\n" + "=" * 30)
    print("Interactive Chat Session")
    print("=" * 30)
    print("Type your messages below. Type 'quit', 'exit', or 'bye' to end.")
    print("Try asking for calculations or text summaries!")
    print()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye', '']:
                print("Goodbye! Thanks for trying HelloAgent!")
                break
                
            if not user_input:
                continue
            
            print("HelloAgent: ", end="", flush=True)
            response = await agent.run(user_input)
            print(response)
            print()
            
        except KeyboardInterrupt:
            print("\nChat session interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print()


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
    
    # Test tools independently
    test_tools()
    
    # Create agent
    agent = create_agent(client)
    
    # Run basic tests
    await run_basic_tests(agent)
    
    # Run tool tests
    await run_tool_tests(agent)
    
    # Start interactive chat
    await interactive_chat(agent)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication interrupted. Goodbye!")
    except Exception as e:
        print(f"Application error: {e}")