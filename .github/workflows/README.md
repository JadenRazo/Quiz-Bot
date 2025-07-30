# GitHub Actions Workflows

This directory contains the CI/CD pipelines for the Quiz Bot project.

## Workflows

### 1. CI Pipeline (`ci.yml`)
Runs on every push (except to main) and pull request.

**What it does:**
- Runs tests with PostgreSQL and Redis
- Checks code quality (linting, formatting, type checking)
- Security scanning
- Builds Docker image
- Vulnerability scanning with Trivy
- Terraform plan for infrastructure changes

### 2. Deploy to Azure (`deploy-azure.yml`)
Runs when pushing to main branch or manually triggered.

**What it does:**
- Builds and pushes Docker image to Azure Container Registry
- Runs Terraform to provision/update infrastructure
- Deploys to Azure Container Apps
- Runs database migrations
- Performs health checks

## Required GitHub Secrets

Configure these in your repository settings under Settings → Secrets and variables → Actions:

### Azure Authentication (OIDC)
- `AZURE_CLIENT_ID` - Azure AD application client ID
- `AZURE_TENANT_ID` - Azure AD tenant ID
- `AZURE_SUBSCRIPTION_ID` - Azure subscription ID

### Terraform State Storage
- `TF_STATE_RESOURCE_GROUP` - Resource group for Terraform state
- `TF_STATE_STORAGE_ACCOUNT` - Storage account name for state
- `TF_STATE_CONTAINER` - Container name for state (usually "tfstate")

### Application Configuration
- `DISCORD_TOKEN` - Discord bot token
- `BOT_OWNER_ID` - Discord user ID of bot owner
- `BOT_APPLICATION_ID` - Discord application ID
- `ALERT_EMAIL` - Email for alerts

### API Keys (at least one required)
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic (Claude) API key
- `GOOGLE_AI_API_KEY` - Google AI (Gemini) API key

### Quiz Prompts
- `STANDARD_PROMPT` - Standard quiz prompt template
- `EDUCATIONAL_PROMPT` - Educational quiz prompt template
- `TRIVIA_PROMPT` - Trivia quiz prompt template
- `CHALLENGE_PROMPT` - Challenge quiz prompt template
- `TRUE_FALSE_PROMPT` - True/false quiz prompt template

## Setting Up Secrets

1. Go to your repository on GitHub
2. Navigate to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add each secret with its name and value

### Azure Setup (One-time)

Before the workflows can run, you need to set up Azure OIDC authentication:

```bash
# Create Azure AD app for GitHub Actions
az ad app create --display-name "quiz-bot-github-oidc"
APP_ID=$(az ad app list --display-name "quiz-bot-github-oidc" --query [].appId -o tsv)
az ad sp create --id $APP_ID

# Configure GitHub repository access
APP_OBJECT_ID=$(az ad app show --id $APP_ID --query id -o tsv)
az ad app federated-credential create --id $APP_OBJECT_ID --parameters @- <<EOF
{
  "name": "github-deploy-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:YOUR_GITHUB_USERNAME/quiz-bot:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF

# Grant permissions
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
az role assignment create --assignee $APP_ID --role Contributor --scope /subscriptions/$SUBSCRIPTION_ID

# Display values for GitHub Secrets
echo "AZURE_CLIENT_ID: $APP_ID"
echo "AZURE_TENANT_ID: $(az account show --query tenantId -o tsv)"
echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION_ID"
```

### Terraform State Storage Setup

```bash
# Create storage for Terraform state
az group create --name tfstate-rg --location eastus
STORAGE_ACCOUNT="tfstate$(date +%s)"
az storage account create --name $STORAGE_ACCOUNT --resource-group tfstate-rg --sku Standard_LRS
az storage container create --name tfstate --account-name $STORAGE_ACCOUNT

echo "TF_STATE_RESOURCE_GROUP: tfstate-rg"
echo "TF_STATE_STORAGE_ACCOUNT: $STORAGE_ACCOUNT"
echo "TF_STATE_CONTAINER: tfstate"
```

## Running Workflows

### Automatic Triggers
- **CI Pipeline**: Runs automatically on push and PR
- **Deploy to Azure**: Runs automatically when pushing to main

### Manual Triggers
Both workflows can be manually triggered:
1. Go to Actions tab
2. Select the workflow
3. Click "Run workflow"
4. Choose the branch
5. Click "Run workflow" button

## Monitoring Deployments

1. **GitHub Actions**: Check the Actions tab for workflow status
2. **Azure Portal**: View resources at https://portal.azure.com
3. **Container App Logs**: 
   ```bash
   az containerapp logs show --name quiz-bot-app --resource-group quiz-bot-rg
   ```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify Azure credentials are correct
   - Check OIDC federation is configured properly
   - Ensure service principal has required permissions

2. **Terraform State Lock**
   - Another deployment might be running
   - Manually unlock if needed: `terraform force-unlock <lock-id>`

3. **Docker Build Failures**
   - Check Dockerfile syntax
   - Verify all required files are present
   - Check for large files that shouldn't be in the image

4. **Deployment Failures**
   - Check Azure Container Apps logs
   - Verify all environment variables are set
   - Check database connectivity

## Cost Optimization

The workflows are designed to minimize costs:
- Uses GitHub-hosted runners (free for public repos)
- Caches Docker layers and dependencies
- Only deploys when pushing to main
- Terraform manages resource lifecycle efficiently