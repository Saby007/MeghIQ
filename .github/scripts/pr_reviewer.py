#!/usr/bin/env python3
"""
PR Reviewer Script for GitHub Actions
Uses Azure OpenAI to generate automated PR feedback and reviews.

This script analyzes pull request changes and generates constructive feedback
using Azure OpenAI GPT models, following best practices for code review.
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
from datetime import datetime

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import AzureError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PRReviewConfig:
    """Configuration class for PR review settings"""
    
    def __init__(self):
        self.azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
        self.deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
        self.api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
        self.max_tokens = int(os.getenv('MAX_REVIEW_TOKENS', '2000'))
        self.temperature = float(os.getenv('REVIEW_TEMPERATURE', '0.3'))
        
        # PR context
        self.pr_title = os.getenv('PR_TITLE', '')
        self.pr_body = os.getenv('PR_BODY', '')
        self.pr_author = os.getenv('PR_AUTHOR', '')
        self.repo_owner = os.getenv('REPO_OWNER', '')
        self.repo_name = os.getenv('REPO_NAME', '')
        self.pr_number = os.getenv('PR_NUMBER', '')
        
        # Validation
        self._validate_config()
    
    def _validate_config(self):
        """Validate required configuration"""
        required_vars = ['azure_endpoint', 'deployment_name']
        missing_vars = [var for var in required_vars if not getattr(self, var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")

class AzureOpenAIPRReviewer:
    """Azure OpenAI-powered PR reviewer"""
    
    def __init__(self, config: PRReviewConfig):
        self.config = config
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Azure OpenAI client with flexible authentication"""
        try:
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            
            if api_key:
                # Use API key authentication (simpler, recommended for most cases)
                logger.info("Using API key authentication")
                self.client = AzureOpenAI(
                    azure_endpoint=self.config.azure_endpoint,
                    api_key=api_key,
                    api_version=self.config.api_version
                )
            else:
                # Use managed identity/service principal authentication
                logger.info("Using Azure AD authentication (Managed Identity/Service Principal)")
                credential = DefaultAzureCredential()
                
                self.client = AzureOpenAI(
                    azure_endpoint=self.config.azure_endpoint,
                    azure_ad_token_provider=credential,
                    api_version=self.config.api_version
                )
            
            logger.info("Azure OpenAI client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {str(e)}")
            raise
    
    def _create_review_prompt(self, pr_context: Dict[str, Any]) -> str:
        """Create a comprehensive prompt for PR review"""
        
        prompt = f"""You are an expert code reviewer conducting a thorough analysis of a GitHub pull request. 
Please provide constructive, actionable feedback following best practices for code review.

**Pull Request Context:**
- Title: {pr_context.get('title', 'N/A')}
- Author: {pr_context.get('author', 'N/A')}
- Repository: {pr_context.get('repo_owner', 'N/A')}/{pr_context.get('repo_name', 'N/A')}
- PR Number: #{pr_context.get('pr_number', 'N/A')}

**PR Description:**
{pr_context.get('body', 'No description provided')}

**Files Changed ({len(pr_context.get('changed_files', []))}):**
{self._format_changed_files(pr_context.get('changed_files', []))}

**Code Changes (Diff):**
```diff
{pr_context.get('diff_content', 'No diff available')[:8000]}  # Limit to prevent token overflow
```

**Review Guidelines:**
1. **Code Quality**: Check for readability, maintainability, and adherence to best practices
2. **Security**: Identify potential security vulnerabilities or concerns
3. **Performance**: Look for performance implications and optimization opportunities
4. **Testing**: Assess test coverage and suggest testing improvements
5. **Documentation**: Evaluate if code changes are properly documented
6. **Architecture**: Consider if changes align with project architecture
7. **Dependencies**: Review any new dependencies or version changes

**Please provide your review in the following structured format:**

## 🤖 **Automated PR Review with Azure OpenAI**

### 📋 **Summary**
[Brief overview of the changes and overall assessment]

### ✅ **Strengths**
[List positive aspects of the PR]

### 🔍 **Areas for Improvement**
[List specific issues, concerns, or suggestions]

### 🔒 **Security Considerations**
[Any security-related observations]

### 🚀 **Performance Notes**
[Performance-related observations]

### 📚 **Documentation & Testing**
[Comments on documentation and testing]

### 🎯 **Recommendations**
[Specific actionable recommendations]

### 📊 **Overall Rating**
[Rate the PR: Excellent ⭐⭐⭐⭐⭐ | Good ⭐⭐⭐⭐ | Needs Work ⭐⭐⭐ | Major Issues ⭐⭐]

---
*Review generated by Azure OpenAI | Model: {self.config.deployment_name} | Timestamp: {datetime.now().isoformat()}*

**Important Notes:**
- Be constructive and helpful in your feedback
- Focus on actionable suggestions
- Consider the context and complexity of changes
- If no significant issues found, acknowledge good practices
- Keep feedback professional and encouraging"""

        return prompt
    
    def _format_changed_files(self, changed_files: List[Dict]) -> str:
        """Format the list of changed files for the prompt"""
        if not changed_files:
            return "No files changed"
        
        formatted_files = []
        for file_info in changed_files[:20]:  # Limit to first 20 files
            filename = file_info.get('filename', 'Unknown')
            status = file_info.get('status', 'modified')
            additions = file_info.get('additions', 0)
            deletions = file_info.get('deletions', 0)
            
            formatted_files.append(f"- `{filename}` ({status}) +{additions}/-{deletions}")
        
        if len(changed_files) > 20:
            formatted_files.append(f"... and {len(changed_files) - 20} more files")
        
        return "\n".join(formatted_files)
    
    def _should_skip_review(self, pr_context: Dict[str, Any]) -> tuple[bool, str]:
        """Determine if review should be skipped"""
        changed_files = pr_context.get('changed_files', [])
        
        # Skip if no files changed
        if not changed_files:
            return True, "No files changed in this PR"
        
        # Skip if only non-code files changed (docs, configs, etc.)
        code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.rs', '.kt', '.swift'}
        has_code_changes = any(
            Path(f.get('filename', '')).suffix.lower() in code_extensions 
            for f in changed_files
        )
        
        if not has_code_changes:
            return True, "No code files changed - only documentation or configuration files"
        
        # Skip very large PRs (over 50 files) to avoid overwhelming reviews
        if len(changed_files) > 50:
            return True, f"PR too large ({len(changed_files)} files) - consider breaking into smaller PRs"
        
        return False, ""
    
    async def generate_review(self, pr_context: Dict[str, Any]) -> Optional[str]:
        """Generate PR review using Azure OpenAI"""
        try:
            # Check if we should skip the review
            should_skip, skip_reason = self._should_skip_review(pr_context)
            if should_skip:
                logger.info(f"Skipping review: {skip_reason}")
                return None
            
            # Create the review prompt
            prompt = self._create_review_prompt(pr_context)
            
            logger.info("Generating PR review with Azure OpenAI...")
            
            # Make the API call
            response = self.client.chat.completions.create(
                model=self.config.deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert code reviewer with extensive experience in software development, security, and best practices. Provide thorough, constructive, and actionable feedback on code changes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=0.9
            )
            
            if response.choices and len(response.choices) > 0:
                review_content = response.choices[0].message.content
                logger.info("Successfully generated PR review")
                return review_content
            else:
                logger.error("No response generated from Azure OpenAI")
                return None
                
        except AzureError as e:
            logger.error(f"Azure OpenAI API error: {str(e)}")
            return f"⚠️ **Review Generation Failed**\n\nAzure OpenAI service temporarily unavailable. Error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error generating review: {str(e)}")
            return f"⚠️ **Review Generation Failed**\n\nAn unexpected error occurred: {str(e)}"

def load_pr_context() -> Dict[str, Any]:
    """Load PR context from environment and files"""
    context = {
        'title': os.getenv('PR_TITLE', ''),
        'body': os.getenv('PR_BODY', ''),
        'author': os.getenv('PR_AUTHOR', ''),
        'repo_owner': os.getenv('REPO_OWNER', ''),
        'repo_name': os.getenv('REPO_NAME', ''),
        'pr_number': os.getenv('PR_NUMBER', ''),
        'changed_files': [],
        'diff_content': ''
    }
    
    # Load files changed
    files_changed_env = os.getenv('FILES_CHANGED', '[]')
    try:
        context['changed_files'] = json.loads(files_changed_env)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse FILES_CHANGED: {e}")
        context['changed_files'] = []
    
    # Load diff content
    try:
        if Path('pr_diff_limited.txt').exists():
            with open('pr_diff_limited.txt', 'r', encoding='utf-8', errors='ignore') as f:
                context['diff_content'] = f.read()
        else:
            logger.warning("pr_diff_limited.txt not found")
    except Exception as e:
        logger.warning(f"Failed to read diff content: {e}")
        context['diff_content'] = ''
    
    return context

def save_review_output(review_content: str):
    """Save review content to output file"""
    try:
        with open('review_output.md', 'w', encoding='utf-8') as f:
            f.write(review_content)
        logger.info("Review output saved to review_output.md")
        
        # Also set GitHub Actions output
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                f.write(f"review-comment={review_content[:1000]}...\n")  # Truncate for output
                
    except Exception as e:
        logger.error(f"Failed to save review output: {e}")

async def main():
    """Main function"""
    try:
        logger.info("Starting PR review process...")
        
        # Load configuration
        config = PRReviewConfig()
        logger.info(f"Configuration loaded - Endpoint: {config.azure_endpoint[:50]}...")
        
        # Load PR context
        pr_context = load_pr_context()
        logger.info(f"PR context loaded - Title: {pr_context['title'][:50]}...")
        
        # Initialize reviewer
        reviewer = AzureOpenAIPRReviewer(config)
        
        # Generate review
        review_content = await reviewer.generate_review(pr_context)
        
        if review_content:
            # Save review output
            save_review_output(review_content)
            logger.info("PR review completed successfully")
        else:
            logger.info("No review generated (PR may have been skipped)")
            
    except Exception as e:
        logger.error(f"Fatal error in PR review process: {str(e)}")
        
        # Create error review
        error_review = f"""## 🤖 **Automated PR Review - Error**

⚠️ **Review Generation Failed**

An error occurred while generating the automated review:
```
{str(e)}
```

Please check the GitHub Actions logs for more details.

---
*Error occurred at: {datetime.now().isoformat()}*
"""
        save_review_output(error_review)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())