# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-07-27

### Added

- NextGen AWS Resilience Hub (V2) integration with GenAI-powered failure mode assessments
- Resilience policy with Pilot Light DR targets (RTO: 15 min, RPO: 5 min)
- Tag-based resource discovery across both regions (`Project: AirportHub`)
- 4 service functions modeling application components (Frontend, API, Database, Scheduled Refresh)
- IAM role for Resilience Hub assessment with AWS managed policy
- README section documenting Resilience Hub architecture and usage
- Back-to-top navigation links in README

### Changed

- Updated deployment plan display to include Resilience Hub
- Added `.kiro/` to `.gitignore`

## [1.2.0] - 2026-07-20

### Added

- Initial multi-region Pilot Light DR architecture
- ARC Region Switch Plan with automated failover/failback
- DocumentDB Global Cluster with cross-region replication
- ECS Fargate + Lambda + CloudFront VPC Origins
- FlightAware scheduled refresh microservice with nested ARC child plan
- Interactive deploy.py and teardown.py scripts
- CloudWatch observability dashboard and alarms

[1.3.0]: https://github.com/aws-samples/sample-multi-region-application-architecture/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/aws-samples/sample-multi-region-application-architecture/releases/tag/v1.2.0
