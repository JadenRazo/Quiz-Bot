variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus"
}

variable "discord_token" {
  description = "Discord bot token"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_ai_api_key" {
  description = "Google AI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "bot_owner_id" {
  description = "Discord ID of the bot owner"
  type        = string
}

variable "bot_application_id" {
  description = "Discord application ID"
  type        = string
}

variable "alert_email" {
  description = "Email for alerts"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "allowed_ip_addresses" {
  description = "List of IP addresses allowed to access the database"
  type        = list(string)
  default     = []
}

# Prompt variables
variable "standard_prompt" {
  description = "Standard quiz prompt template"
  type        = string
  sensitive   = true
}

variable "educational_prompt" {
  description = "Educational quiz prompt template"
  type        = string
  sensitive   = true
}

variable "trivia_prompt" {
  description = "Trivia quiz prompt template"
  type        = string
  sensitive   = true
}

variable "challenge_prompt" {
  description = "Challenge quiz prompt template"
  type        = string
  sensitive   = true
}

variable "true_false_prompt" {
  description = "True/false quiz prompt template"
  type        = string
  sensitive   = true
}