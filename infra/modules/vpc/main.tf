# VPC module for Radius Lambda isolation.
# All Lambda functions run in private subnets with no internet egress.
# AWS services are reached exclusively through VPC endpoints, which keeps
# all traffic on the AWS private network (no NAT gateway needed).
#
# Interface endpoint cost: ~$7/month each in us-east-1.
# With 5 Interface endpoints = ~$35/month before data charges.
# The Gateway endpoint (DynamoDB) is free.

locals {
  common_tags = merge(
    {
      Module      = "vpc"
      Environment = var.environment
    },
    var.tags
  )

  az_count     = length(var.availability_zones)
  subnet_cidrs = [for i in range(local.az_count) : cidrsubnet(var.vpc_cidr, 8, i)]
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------
resource "aws_vpc" "radius" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, { Name = "${var.prefix}-vpc" })
}

# ---------------------------------------------------------------------------
# Private subnets — one per AZ for Lambda HA placement
# ---------------------------------------------------------------------------
resource "aws_subnet" "private" {
  count = local.az_count

  vpc_id            = aws_vpc.radius.id
  cidr_block        = local.subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  # No public IPs — all egress goes through VPC endpoints
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "${var.prefix}-private-${var.availability_zones[count.index]}"
    Tier = "private"
  })
}

# ---------------------------------------------------------------------------
# Security group for Lambda functions
# Inbound: none (Lambda functions don't accept inbound connections)
# Outbound: HTTPS only, to VPC endpoint network interfaces
# ---------------------------------------------------------------------------
resource "aws_security_group" "lambda" {
  name        = "${var.prefix}-lambda-sg"
  description = "Security group for Radius Lambda functions — HTTPS egress to VPC endpoints only"
  vpc_id      = aws_vpc.radius.id

  egress {
    description = "HTTPS to VPC endpoints"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(local.common_tags, { Name = "${var.prefix}-lambda-sg" })
}

# ---------------------------------------------------------------------------
# Security group for VPC Interface endpoints
# Accepts HTTPS from Lambda security group only
# ---------------------------------------------------------------------------
resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.prefix}-vpce-sg"
  description = "Security group for Radius VPC endpoints — accepts HTTPS from Lambda SG"
  vpc_id      = aws_vpc.radius.id

  ingress {
    description     = "HTTPS from Lambda functions"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  tags = merge(local.common_tags, { Name = "${var.prefix}-vpce-sg" })
}

# ---------------------------------------------------------------------------
# Route table for private subnets
# No internet gateway or NAT — traffic routes only to VPC endpoints
# ---------------------------------------------------------------------------
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.radius.id
  tags   = merge(local.common_tags, { Name = "${var.prefix}-private-rt" })
}

resource "aws_route_table_association" "private" {
  count          = local.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ---------------------------------------------------------------------------
# Gateway endpoint — DynamoDB (free, no hourly charge)
# Routes DynamoDB traffic over the AWS private network
# ---------------------------------------------------------------------------
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.radius.id
  service_name      = "com.amazonaws.${var.aws_region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id]

  tags = merge(local.common_tags, { Name = "${var.prefix}-vpce-dynamodb" })
}

# ---------------------------------------------------------------------------
# Interface endpoints — SNS, SQS, Secrets Manager, Lambda, SSM
# Each ~$7/month in us-east-1 before data transfer
# ---------------------------------------------------------------------------
locals {
  interface_services = {
    sns            = "com.amazonaws.${var.aws_region}.sns"
    sqs            = "com.amazonaws.${var.aws_region}.sqs"
    secretsmanager = "com.amazonaws.${var.aws_region}.secretsmanager"
    lambda         = "com.amazonaws.${var.aws_region}.lambda"
    ssm            = "com.amazonaws.${var.aws_region}.ssm"
  }
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.interface_services

  vpc_id              = aws_vpc.radius.id
  service_name        = each.value
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, { Name = "${var.prefix}-vpce-${each.key}" })
}
