# PR Review Workflow Status

## Workflow Badge

Add this badge to your repository's README.md to show the workflow status:

```markdown
![PR Review Workflow](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions/workflows/pr-review-azure-openai.yml/badge.svg)
```

## Quick Setup Checklist

- [ ] Azure OpenAI resource created
- [ ] Service principal created with appropriate permissions
- [ ] GitHub secrets configured:
  - [ ] `AZURE_CREDENTIALS`
  - [ ] `AZURE_OPENAI_ENDPOINT`
  - [ ] `AZURE_OPENAI_DEPLOYMENT_NAME`
  - [ ] `AZURE_OPENAI_API_VERSION`
- [ ] Workflow files copied to repository
- [ ] Test setup script executed successfully
- [ ] First test PR created

## Workflow Files

```
.github/
├── workflows/
│   └── pr-review-azure-openai.yml    # Main workflow
├── scripts/
│   ├── pr_reviewer.py               # Review generation script
│   ├── requirements.txt             # Python dependencies
│   └── test_setup.py               # Setup validation script
├── config-sample.env               # Configuration template
└── README.md                       # Documentation
```

## Testing the Setup

1. **Local Testing**:
   ```bash
   cd .github/scripts
   pip install -r requirements.txt
   python test_setup.py
   ```

2. **Create a Test PR**:
   - Make a small code change
   - Create a pull request
   - Check the Actions tab for workflow execution
   - Review the generated feedback

## Monitoring

- **GitHub Actions**: Monitor workflow runs in the Actions tab
- **Azure OpenAI**: Monitor usage and costs in Azure Portal
- **Review Quality**: Gather feedback from team members

## Support

If you encounter issues:

1. Check the [troubleshooting section](README.md#-monitoring-and-troubleshooting) in README.md
2. Verify all secrets are correctly configured
3. Check GitHub Actions logs for detailed error messages
4. Test Azure OpenAI connection using the test script