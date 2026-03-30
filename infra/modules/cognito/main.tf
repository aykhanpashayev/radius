# Cognito User Pool for Radius dashboard authentication.
# Admin-only user creation — no self-registration.

resource "aws_cognito_user_pool" "radius" {
  name = "${var.prefix}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 12
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = var.tags
}

resource "aws_cognito_user_pool_client" "dashboard" {
  name         = "${var.prefix}-dashboard-client"
  user_pool_id = aws_cognito_user_pool.radius.id

  generate_secret = false # Must be false for browser-based apps

  access_token_validity  = 1 # hours
  id_token_validity      = 1 # hours
  refresh_token_validity = 7 # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  allowed_oauth_flows_user_pool_client = true
  supported_identity_providers         = ["COGNITO"]
}

resource "aws_cognito_user_pool_domain" "radius" {
  # Must be globally unique — prefix includes env to avoid collisions
  domain       = var.prefix
  user_pool_id = aws_cognito_user_pool.radius.id
}
