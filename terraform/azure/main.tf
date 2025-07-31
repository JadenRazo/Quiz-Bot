terraform {
  required_version = ">= 1.6.0"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  
  backend "azurerm" {
    # Backend configuration is provided via CLI flags
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
  use_oidc = true
}

# Resource naming
locals {
  project_name = "quiz-bot"
  environment  = "prod"
  location     = var.location
  
  # Consistent naming
  resource_prefix = "${local.project_name}-${local.environment}"
  
  # Tags
  common_tags = {
    Project     = "Quiz Bot"
    Environment = local.environment
    ManagedBy   = "Terraform"
    Owner       = var.bot_owner_id
  }
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "${local.resource_prefix}-rg"
  location = local.location
  tags     = local.common_tags
}

# Container Registry
resource "azurerm_container_registry" "main" {
  name                = "${replace(local.project_name, "-", "")}acr${local.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true
  
  tags = local.common_tags
}

# PostgreSQL Server
resource "random_password" "postgres" {
  length  = 32
  special = true
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                = "${local.resource_prefix}-postgres"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  
  version                      = "15"
  administrator_login          = "quizbot"
  administrator_password       = random_password.postgres.result
  storage_mb                   = 32768
  backup_retention_days        = 7
  sku_name                    = "B_Standard_B1ms"
  zone                        = "1"
  
  tags = local.common_tags
}

# PostgreSQL Database
resource "azurerm_postgresql_flexible_server_database" "main" {
  name      = "quizbot"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Allow Azure services to access PostgreSQL
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.resource_prefix}-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  
  tags = local.common_tags
}

# Container Apps Environment
resource "azurerm_container_app_environment" "main" {
  name                       = "${local.resource_prefix}-env"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  
  tags = local.common_tags
}

# Key Vault for secrets
resource "azurerm_key_vault" "main" {
  name                = "${replace(local.project_name, "-", "")}kv${local.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
  
  tags = local.common_tags
}

data "azurerm_client_config" "current" {}

# Key Vault Access Policy
resource "azurerm_key_vault_access_policy" "terraform" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id
  
  secret_permissions = [
    "Get", "List", "Set", "Delete", "Purge"
  ]
}

# Store secrets in Key Vault
resource "azurerm_key_vault_secret" "discord_token" {
  name         = "discord-token"
  value        = var.discord_token
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "openai-api-key"
  value        = var.openai_api_key
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "anthropic_api_key" {
  name         = "anthropic-api-key"
  value        = var.anthropic_api_key
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "google_ai_api_key" {
  name         = "google-ai-api-key"
  value        = var.google_ai_api_key
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

# Store prompts in Key Vault
resource "azurerm_key_vault_secret" "standard_prompt" {
  name         = "standard-prompt"
  value        = var.standard_prompt
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "educational_prompt" {
  name         = "educational-prompt"
  value        = var.educational_prompt
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "trivia_prompt" {
  name         = "trivia-prompt"
  value        = var.trivia_prompt
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "challenge_prompt" {
  name         = "challenge-prompt"
  value        = var.challenge_prompt
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

resource "azurerm_key_vault_secret" "true_false_prompt" {
  name         = "true-false-prompt"
  value        = var.true_false_prompt
  key_vault_id = azurerm_key_vault.main.id
  
  depends_on = [azurerm_key_vault_access_policy.terraform]
}

# Container App
resource "azurerm_container_app" "main" {
  name                         = "${local.resource_prefix}-app"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  
  template {
    container {
      name   = "quiz-bot"
      image  = "${azurerm_container_registry.main.login_server}/quiz-bot:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"
      
      # Environment variables
      env {
        name  = "DISCORD_TOKEN"
        value = var.discord_token
      }
      
      env {
        name  = "DB_HOST"
        value = azurerm_postgresql_flexible_server.main.fqdn
      }
      
      env {
        name  = "DB_PORT"
        value = "5432"
      }
      
      env {
        name  = "DB_NAME"
        value = azurerm_postgresql_flexible_server_database.main.name
      }
      
      env {
        name  = "DB_USER"
        value = azurerm_postgresql_flexible_server.main.administrator_login
      }
      
      env {
        name  = "DB_PASSWORD"
        value = azurerm_postgresql_flexible_server.main.administrator_password
      }
      
      env {
        name  = "DB_SSL_MODE"
        value = "require"
      }
      
      env {
        name  = "OPENAI_API_KEY"
        value = var.openai_api_key
      }
      
      env {
        name  = "ANTHROPIC_API_KEY"
        value = var.anthropic_api_key
      }
      
      env {
        name  = "GOOGLE_AI_API_KEY"
        value = var.google_ai_api_key
      }
      
      env {
        name  = "BOT_OWNER_ID"
        value = var.bot_owner_id
      }
      
      env {
        name  = "BOT_APPLICATION_ID"
        value = var.bot_application_id
      }
      
      # Prompt environment variables
      env {
        name  = "STANDARD_PROMPT"
        value = var.standard_prompt
      }
      
      env {
        name  = "EDUCATIONAL_PROMPT"
        value = var.educational_prompt
      }
      
      env {
        name  = "TRIVIA_PROMPT"
        value = var.trivia_prompt
      }
      
      env {
        name  = "CHALLENGE_PROMPT"
        value = var.challenge_prompt
      }
      
      env {
        name  = "TRUE_FALSE_PROMPT"
        value = var.true_false_prompt
      }
    }
    
    min_replicas = 1
    max_replicas = 3
  }
  
  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "container-registry-password"
  }
  
  secret {
    name  = "container-registry-password"
    value = azurerm_container_registry.main.admin_password
  }
  
  ingress {
    external_enabled = true
    target_port      = 8000
    
    traffic_weight {
      percentage = 100
    }
  }
  
  tags = local.common_tags
}

# Application Insights
resource "azurerm_application_insights" "main" {
  name                = "${local.resource_prefix}-insights"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  application_type    = "other"
  workspace_id        = azurerm_log_analytics_workspace.main.id
  
  tags = local.common_tags
}