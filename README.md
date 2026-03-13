# Radius - Cloud Security Platform

Radius is a cloud security platform designed to measure and reduce the blast radius of identity-based attacks in AWS Organizations.

## Overview

The system monitors CloudTrail control-plane events, evaluates suspicious identity behavior, and calculates Blast Radius Scores for IAM identities.

### Key Features

- **Identity Risk Analysis**: Track and analyze IAM identity behavior across AWS accounts
- **Suspicious Activity Detection**: Identify potential security threats in real-time
- **Incident Tracking**: Manage and investigate security incidents
- **Explainable Security Analytics**: Transparent, rule-based scoring and detection

### Architecture

Radius uses a serverless event-driven architecture built on AWS:

- **CloudTrail**: Captures AWS API activity across the organization
- **EventBridge**: Routes events to processing functions
- **Lambda**: Processes events, detects threats, and manages incidents
- **DynamoDB**: Stores identity profiles, scores, incidents, and events
- **API Gateway**: Provides REST API for dashboard access
- **SNS**: Sends alerts for high-severity incidents

## Project Structure

```
radius/
├── backend/              # Lambda functions and backend logic
│   ├── common/          # Shared utilities for Lambda functions
│   ├── functions/       # Individual Lambda function implementations
│   └── tests/           # Backend unit and integration tests
├── infra/               # Terraform infrastructure as code
│   ├── modules/         # Reusable Terraform modules
│   └── envs/            # Environment-specific configurations (dev, prod)
├── docs/                # Architecture and API documentation
├── sample-data/         # Example CloudTrail events for testing
├── scripts/             # Deployment and utility scripts
└── frontend/            # React dashboard (future phase)
```

## Phase 2 Scope

**Current Phase**: Phase 2 - Infrastructure and Backend Foundation

Phase 2 establishes the complete infrastructure foundation and service skeletons:

- ✅ Modular Terraform infrastructure with dev/prod environments
- ✅ Five DynamoDB tables with 13 Global Secondary Indexes
- ✅ Six Lambda functions with IAM roles and CloudWatch integration
- ✅ CloudTrail configuration with EventBridge routing
- ✅ API Gateway with 10 REST endpoints
- ✅ SNS alerting infrastructure
- ✅ CloudWatch dashboards, metrics, and alarms
- ✅ Sample CloudTrail events and testing scripts

**Note**: Detection_Engine and Score_Engine are PLACEHOLDER functions in Phase 2. Full detection rules and scoring algorithms will be implemented in later phases.

## Prerequisites

- **AWS Account**: AWS account with appropriate permissions
- **Terraform**: Version 1.5+ ([Installation Guide](https://developer.hashicorp.com/terraform/downloads))
- **Python**: Version 3.11+ ([Installation Guide](https://www.python.org/downloads/))
- **AWS CLI**: Configured with credentials ([Installation Guide](https://aws.amazon.com/cli/))

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd radius
```

### 2. Configure AWS Credentials

```bash
aws configure
```

### 3. Deploy Infrastructure

```bash
# Build Lambda functions
./scripts/build-lambdas.sh

# Deploy to dev environment
./scripts/deploy-infra.sh --env dev

# Verify deployment
./scripts/verify-deployment.sh --env dev
```

### 4. Test the Pipeline

```bash
# Inject sample CloudTrail events
python scripts/inject-events.py --env dev --directory sample-data/

# Seed test data
python scripts/seed-dev-data.py --env dev
```

## Development

### Backend Development

Lambda functions are located in `backend/functions/`. Each function has its own directory with:

- `handler.py`: Lambda entry point
- `requirements.txt`: Python dependencies
- Function-specific modules

Shared utilities are in `backend/common/`:

- `logging_utils.py`: Structured JSON logging
- `dynamodb_utils.py`: DynamoDB operations
- `validation.py`: Input validation
- `errors.py`: Custom exceptions

### Infrastructure Development

Terraform modules are in `infra/modules/`. Each module is self-contained with:

- `main.tf`: Resource definitions
- `variables.tf`: Input variables
- `outputs.tf`: Output values
- Additional files for specific resources (e.g., `iam.tf`, `gsi.tf`)

Environment configurations are in `infra/envs/dev/` and `infra/envs/prod/`.

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Database Schema](docs/database-schema.md)
- [API Reference](docs/api-reference.md)
- [Terraform Modules](docs/terraform-modules.md)
- [Deployment Guide](docs/deployment.md)
- [Monitoring Guide](docs/monitoring.md)
- [Phase 2 Scope](docs/phase-2-scope.md)

## Testing

### Unit Tests

```bash
cd backend
python -m pytest tests/unit/
```

### Integration Tests

```bash
cd backend
python -m pytest tests/integration/
```

### Property-Based Tests

```bash
cd backend
python -m pytest tests/property/
```

## Monitoring

CloudWatch dashboards are available in the AWS Console:

- **Lambda Metrics**: Invocations, errors, duration, throttles
- **DynamoDB Metrics**: Consumed capacity, throttled requests
- **API Gateway Metrics**: Request count, latency, error rates
- **EventBridge Metrics**: Rule invocations

CloudWatch alarms are configured for:

- Lambda error rates > 5%
- Lambda duration approaching timeout
- DynamoDB throttled requests > 10/min
- Dead-letter queue messages > 0
- API Gateway 5xx errors > 1%

## Cost Optimization

Radius is designed to be cost-aware:

- **On-demand DynamoDB billing**: Pay only for what you use
- **Serverless Lambda**: No idle compute costs
- **Event-driven processing**: No continuous scanning
- **TTL on Event_Summary**: Automatic cleanup of old events
- **S3 lifecycle policies**: Archive CloudTrail logs to Glacier

**Dev Environment**: Minimal resource provisioning, 7-day log retention
**Prod Environment**: High availability, 30-day log retention

## Security

- **Encryption at rest**: All DynamoDB tables and S3 buckets use KMS encryption
- **Encryption in transit**: API Gateway uses HTTPS, SNS messages encrypted
- **IAM least privilege**: Each Lambda function has minimal required permissions
- **CloudTrail log validation**: Ensures log integrity
- **VPC isolation**: Lambda functions use VPC when required

## Contributing

1. Create a feature branch from `main`
2. Make your changes following the coding standards
3. Write tests for new functionality
4. Update documentation as needed
5. Submit a pull request

## License

[License information to be added]

## Support

For issues, questions, or contributions, please [open an issue](https://github.com/your-org/radius/issues).

## Roadmap

- **Phase 1**: ✅ Architecture design and planning
- **Phase 2**: 🚧 Infrastructure and backend foundation (current)
- **Phase 3**: Detection rules and suspicious behavior analysis
- **Phase 4**: Blast radius scoring algorithms
- **Phase 5**: Frontend dashboard
- **Phase 6**: Advanced analytics and reporting
