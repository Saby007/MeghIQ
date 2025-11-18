# Automated PR Review with Azure OpenAI

This GitHub Actions workflow provides automated pull request reviews using Azure OpenAI GPT models. It analyzes code changes, provides constructive feedback, and helps maintain code quality standards.

## 🚀 Features

- **Intelligent Code Analysis**: Uses Azure OpenAI GPT-4 to analyze code changes
- **Structured Reviews**: Provides organized feedback covering quality, security, performance, and best practices
- **Security Scanning**: Includes automated security vulnerability detection
- **Customizable**: Configurable review criteria and AI model parameters
- **Cost Effective**: Uses Azure Managed Identity for secure, cost-effective authentication
- **Non-Intrusive**: Only reviews when code files are changed, skips documentation-only PRs

## 📋 What the Review Covers

- **Code Quality**: Readability, maintainability, and best practices
- **Security**: Potential vulnerabilities and security concerns
- **Performance**: Optimization opportunities and performance implications
- **Testing**: Test coverage assessment and suggestions
- **Documentation**: Code documentation quality
- **Architecture**: Alignment with project architecture patterns

## 🛠️ Setup Instructions

### Prerequisites

1. **Azure OpenAI Resource**: You need an Azure OpenAI resource with a deployed model (GPT-4 recommended)
2. **GitHub Repository**: Admin access to configure secrets and actions
3. **Azure Service Principal**: For GitHub Actions authentication with Azure

### Step 1: Create Azure Service Principal

Create a service principal for GitHub Actions to authenticate with Azure:

```bash
# Login to Azure
az login

# Create service principal
az ad sp create-for-rbac --name "github-actions-pr-reviewer" \
  --role "Cognitive Services OpenAI User" \
  --scopes "/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/{OPENAI_RESOURCE_NAME}" \
  --sdk-auth

# Note: Replace {SUBSCRIPTION_ID}, {RESOURCE_GROUP}, and {OPENAI_RESOURCE_NAME} with your actual values
```

This will output JSON credentials that you'll use in the next step.

### Step 2: Configure GitHub Secrets

Add the following secrets to your GitHub repository (Settings → Secrets and variables → Actions):

#### Required Secrets:

1. **`AZURE_CREDENTIALS`**: The entire JSON output from the service principal creation
   ```json
   {
     "clientId": "...",
     "clientSecret": "...",
     "subscriptionId": "...",
     "tenantId": "...",
     "activeDirectoryEndpointUrl": "...",
     "resourceManagerEndpointUrl": "...",
     "activeDirectoryGraphResourceId": "...",
     "sqlManagementEndpointUrl": "...",
     "galleryEndpointUrl": "...",
     "managementEndpointUrl": "..."
   }
   ```

2. **`AZURE_OPENAI_ENDPOINT`**: Your Azure OpenAI endpoint URL
   ```
   https://your-openai-resource.openai.azure.com/
   ```

3. **`AZURE_OPENAI_DEPLOYMENT_NAME`**: Your deployed model name
   ```
   gpt-4
   ```

4. **`AZURE_OPENAI_API_VERSION`**: API version (recommended: `2024-02-15-preview`)

#### Optional Secrets:

- **`MAX_REVIEW_TOKENS`**: Maximum tokens for review generation (default: 2000)
- **`REVIEW_TEMPERATURE`**: AI creativity level 0.0-1.0 (default: 0.3)

### Step 3: Copy Workflow Files

Copy the following files to your repository:

```
.github/
├── workflows/
│   └── pr-review-azure-openai.yml
└── scripts/
    ├── pr_reviewer.py
    └── requirements.txt
```

### Step 4: Configure Workflow (Optional)

The workflow is pre-configured with sensible defaults, but you can customize it by editing `.github/workflows/pr-review-azure-openai.yml`:

#### Trigger Configuration:
```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [ main, develop ]  # Customize target branches
```

#### File Filters:
To only review specific file types, add path filters:
```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [ main, develop ]
    paths:
      - '**.py'
      - '**.js'
      - '**.ts'
      - '**.java'
```

## 🔧 Advanced Configuration

### Custom Review Prompts

To customize the review criteria, edit the `_create_review_prompt` method in `.github/scripts/pr_reviewer.py`:

```python
def _create_review_prompt(self, pr_context: Dict[str, Any]) -> str:
    # Add your custom review guidelines here
    custom_guidelines = """
    **Custom Review Guidelines:**
    - Check for compliance with company coding standards
    - Verify API documentation is updated
    - Ensure error handling follows established patterns
    """
```

### Skip Conditions

Customize when reviews should be skipped by modifying `_should_skip_review`:

```python
def _should_skip_review(self, pr_context: Dict[str, Any]) -> tuple[bool, str]:
    # Add custom skip logic
    if pr_context.get('title', '').startswith('[SKIP-REVIEW]'):
        return True, "Review skipped per PR title directive"
```

## 🔒 Security Considerations

### Best Practices Implemented:

1. **Managed Identity**: Uses Azure Managed Identity instead of API keys
2. **Least Privilege**: Service principal has minimal required permissions
3. **Token Limits**: Implements token limits to prevent excessive API usage
4. **Input Validation**: Validates and sanitizes all inputs
5. **Error Handling**: Graceful error handling with informative messages

### Security Scanning:

The workflow includes automated security scanning:
- **CodeQL Analysis**: For supported languages
- **Bandit**: Python security vulnerability scanner
- **Safety**: Python package vulnerability checker

## 📊 Monitoring and Troubleshooting

### GitHub Actions Logs

Monitor the workflow execution in your repository's "Actions" tab. Each run provides detailed logs for troubleshooting.

### Common Issues:

1. **Authentication Failures**:
   - Verify `AZURE_CREDENTIALS` secret is correctly formatted
   - Check service principal permissions

2. **API Rate Limits**:
   - Azure OpenAI has rate limits based on your subscription
   - The workflow implements retry logic with backoff

3. **Token Limit Exceeded**:
   - Large PRs may exceed token limits
   - The workflow automatically truncates diff content

4. **No Review Generated**:
   - Check if PR only contains non-code files
   - Verify Azure OpenAI deployment is healthy

### Debugging Tips:

1. Enable debug logging by adding this environment variable to the workflow:
   ```yaml
   env:
     ACTIONS_STEP_DEBUG: true
   ```

2. Check the security scan artifacts for additional insights

## 📈 Usage Analytics

Track workflow usage through:
- GitHub Actions usage metrics (Settings → Billing → Actions)
- Azure OpenAI usage in Azure Portal
- Review comment engagement in PRs

## 🔄 Updates and Maintenance

### Regular Tasks:

1. **Update Dependencies**: Keep `requirements.txt` dependencies current
2. **Model Updates**: Consider upgrading to newer OpenAI models when available
3. **Review Prompts**: Refine review prompts based on team feedback
4. **Security**: Rotate service principal credentials periodically

### Version Updates:

When updating this workflow:
1. Test changes in a fork first
2. Update version numbers in requirements.txt
3. Review Azure OpenAI API version compatibility
4. Update documentation as needed

## 💡 Tips for Better Reviews

### For Repository Maintainers:

1. **Clear PR Templates**: Use PR templates to provide context for the AI
2. **Descriptive Commits**: Good commit messages help the AI understand intent
3. **Reasonable PR Size**: Smaller PRs get better, more focused reviews
4. **Team Guidelines**: Customize prompts to match your team's standards

### For Contributors:

1. **Descriptive PR Titles**: Help the AI understand the purpose
2. **Detailed Descriptions**: Provide context in PR descriptions
3. **Self-Review First**: Address obvious issues before creating PR
4. **Respond to Feedback**: Engage with the AI suggestions constructively

## 🤝 Contributing

To improve this workflow:

1. Fork the repository
2. Make your changes
3. Test with your own Azure OpenAI resource
4. Submit a pull request with detailed description

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Related Resources

- [Azure OpenAI Service Documentation](https://docs.microsoft.com/en-us/azure/cognitive-services/openai/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Azure CLI Reference](https://docs.microsoft.com/en-us/cli/azure/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)

## ❓ Support

For issues and questions:

1. Check the troubleshooting section above
2. Review GitHub Actions logs
3. Check Azure OpenAI service health
4. Create an issue in this repository with detailed error information

---

**Note**: This workflow uses Azure OpenAI and may incur costs based on your usage. Monitor your Azure billing and set up appropriate alerts.