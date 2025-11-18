#!/usr/bin/env python3
"""
Test script to validate Azure OpenAI setup for PR review workflow
Run this script locally to test your configuration before using in GitHub Actions.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential

def test_azure_openai_connection():
    """Test Azure OpenAI connection and model deployment"""
    
    print("🧪 Testing Azure OpenAI Configuration")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Required environment variables
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
    
    print(f"Endpoint: {endpoint}")
    print(f"Deployment: {deployment}")
    print(f"API Version: {api_version}")
    print()
    
    if not endpoint:
        print("❌ AZURE_OPENAI_ENDPOINT not found in environment")
        return False
    
    try:
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        
        print("🤖 Initializing Azure OpenAI client...")
        if api_key:
            print("🔐 Using API key authentication...")
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version
            )
        else:
            print("🔐 Using Azure AD authentication...")
            credential = DefaultAzureCredential()
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                azure_ad_token_provider=credential,
                api_version=api_version
            )
        
        print("📤 Testing chat completion...")
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that responds concisely."
                },
                {
                    "role": "user", 
                    "content": "Say 'Hello from Azure OpenAI!' to confirm the connection is working."
                }
            ],
            max_tokens=50,
            temperature=0.1
        )
        
        if response.choices:
            ai_response = response.choices[0].message.content
            print(f"✅ Success! AI Response: {ai_response}")
            print()
            print("🎉 Configuration test passed!")
            print("Your Azure OpenAI setup is ready for the PR review workflow.")
            return True
        else:
            print("❌ No response received from Azure OpenAI")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print()
        print("💡 Common solutions:")
        print("1. Run 'az login' to authenticate with Azure")
        print("2. Verify your Azure OpenAI resource name and deployment")
        print("3. Check that your account has access to the OpenAI resource")
        print("4. Ensure the deployment name matches exactly (case-sensitive)")
        return False

def test_pr_reviewer_script():
    """Test the PR reviewer script with mock data"""
    
    print("\n" + "=" * 50)
    print("🧪 Testing PR Reviewer Script")
    print("=" * 50)
    
    try:
        # Set mock environment variables for testing
        os.environ.update({
            'PR_TITLE': 'Test PR: Add new feature',
            'PR_BODY': 'This is a test PR for validating the review workflow.',
            'PR_AUTHOR': 'test-user',
            'REPO_OWNER': 'test-org',
            'REPO_NAME': 'test-repo', 
            'PR_NUMBER': '123',
            'FILES_CHANGED': '[{"filename": "test.py", "status": "modified", "additions": 10, "deletions": 2}]'
        })
        
        # Create mock diff file
        with open('pr_diff_limited.txt', 'w') as f:
            f.write("""
diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,13 @@
+def hello_world():
+    \"\"\"A simple hello world function\"\"\"
+    print("Hello, World!")
+    return "success"
+
 def main():
-    pass
+    result = hello_world()
+    if result == "success":
+        print("Function executed successfully")
+    else:
+        print("Function failed")

 if __name__ == "__main__":
     main()
""")
        
        # Import and test the PR reviewer
        sys.path.insert(0, '.github/scripts')
        from pr_reviewer import PRReviewConfig, AzureOpenAIPRReviewer, load_pr_context
        
        print("📋 Loading PR context...")
        pr_context = load_pr_context()
        print(f"✅ PR context loaded: {pr_context['title']}")
        
        print("⚙️  Initializing reviewer...")
        config = PRReviewConfig()
        reviewer = AzureOpenAIPRReviewer(config)
        print("✅ Reviewer initialized")
        
        print("🤖 Generating test review (this may take a moment)...")
        async def run_test():
            review = await reviewer.generate_review(pr_context)
            if review:
                print("✅ Review generated successfully!")
                print(f"Review preview: {review[:200]}...")
                
                # Save test review
                with open('test_review_output.md', 'w') as f:
                    f.write(review)
                print("💾 Full review saved to 'test_review_output.md'")
                return True
            else:
                print("❌ No review generated")
                return False
        
        result = asyncio.run(run_test())
        
        # Cleanup
        if os.path.exists('pr_diff_limited.txt'):
            os.remove('pr_diff_limited.txt')
            
        return result
        
    except Exception as e:
        print(f"❌ Error testing PR reviewer: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🚀 Azure OpenAI PR Review Workflow - Configuration Test")
    print("=" * 60)
    print()
    
    # Test 1: Azure OpenAI connection
    openai_test_passed = test_azure_openai_connection()
    
    if openai_test_passed:
        # Test 2: PR reviewer script
        reviewer_test_passed = test_pr_reviewer_script()
        
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)
        print(f"Azure OpenAI Connection: {'✅ PASS' if openai_test_passed else '❌ FAIL'}")
        print(f"PR Reviewer Script: {'✅ PASS' if reviewer_test_passed else '❌ FAIL'}")
        
        if openai_test_passed and reviewer_test_passed:
            print("\n🎉 All tests passed! Your setup is ready for GitHub Actions.")
            print("\nNext steps:")
            print("1. Add the required secrets to your GitHub repository")
            print("2. Commit the workflow files to your repository")
            print("3. Create a test PR to see the workflow in action")
        else:
            print("\n⚠️  Some tests failed. Please resolve the issues above.")
            sys.exit(1)
    else:
        print("\n❌ Azure OpenAI connection test failed.")
        print("Please fix the connection issues before proceeding.")
        sys.exit(1)

if __name__ == "__main__":
    main()