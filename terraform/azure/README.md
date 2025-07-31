# Quiz Bot - Azure Terraform Configuration

This directory contains the Terraform configuration for deploying the Quiz Bot to Azure.

## Resources Created

- **Resource Group**: Container for all resources
- **Container Registry**: Private Docker registry for bot images
- **PostgreSQL Flexible Server**: Managed database with automatic backups
- **Container Apps**: Serverless container hosting for the bot
- **Key Vault**: Secure storage for secrets
- **Application Insights**: Monitoring and diagnostics
- **Log Analytics Workspace**: Centralized logging

## Prerequisites

1. Azure CLI installed and authenticated
2. Terraform 1.6.0 or higher
3. GitHub Actions configured with required secrets

## Setup

1. **Initialize Terraform Backend** (one-time setup):
   ```bash
   # This is handled by GitHub Actions, but for local testing:
   terraform init \
     -backend-config="resource_group_name=$TF_STATE_RESOURCE_GROUP" \
     -backend-config="storage_account_name=$TF_STATE_STORAGE_ACCOUNT" \
     -backend-config="container_name=$TF_STATE_CONTAINER" \
     -backend-config="key=terraform.tfstate"
   ```

2. **Create terraform.tfvars**:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

3. **Plan Deployment**:
   ```bash
   terraform plan
   ```

4. **Apply Configuration**:
   ```bash
   terraform apply
   ```

## Important Notes

- **Never commit** `terraform.tfvars`, `*.tfstate`, or `deployment-info.json`
- All deployments should be done via GitHub Actions
- The `.terraform/` directory contains large binary files and should not be committed
- Sensitive values should be passed via GitHub Secrets in CI/CD

## Cost Estimation

Monthly costs (approximate):
- Container Apps: ~$15-20 (with auto-scaling)
- PostgreSQL: ~$15 (Basic tier)
- Container Registry: ~$5
- Application Insights: ~$2-5
- **Total**: ~$35-45/month

## Destroying Resources

To tear down all resources:
```bash
terraform destroy
```

**Warning**: This will delete all data including the database!