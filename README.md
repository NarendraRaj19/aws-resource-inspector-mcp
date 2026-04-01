# AWS Resource Inspector MCP Server

A Model Context Protocol (MCP) server that enables Claude to interact with AWS resources directly. Built as a learning project to understand MCP architecture and AWS SDK integration.

## Features

### Core Capabilities
- ✅ **EC2 Inspector** - List instances with filtering by region and state
- ✅ **S3 Inspector** - List buckets with region and creation date details
- ✅ **Lambda Inspector** - List functions with runtime, memory, and timeout info
- ✅ **DynamoDB Inspector** - List tables and get detailed table information
- ✅ **Cost Analysis** - Get current month's AWS costs broken down by service
- ✅ **CloudWatch Metrics** - CPU utilization for EC2, invocation metrics for Lambda
- ✅ **Tag Search** - Search resources across EC2, S3, and Lambda by tags
- ✅ **Formatted Output** - Clean tables instead of JSON dumps

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Desktop                          │
│                      (MCP Client)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │ JSON-RPC over stdin/stdout
                       │
┌──────────────────────▼──────────────────────────────────────┐
│           AWS Resource Inspector MCP Server                  │
│                   (Python Process)                           │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   EC2 API   │  │   S3 API     │  │ Lambda API   │       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ DynamoDB    │  │ CloudWatch   │  │ Cost Explorer│       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────┬──────────────────────────────────────┘
                       │ boto3 SDK (HTTPS)
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      AWS API                                 │
│          (EC2, S3, Lambda, DynamoDB, etc.)                  │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Python 3.10+
  - AWS CLI configured with valid credentials
  - Claude Desktop app

## Installation

1. **Clone the repository:**
```bash
git clone <your-repo-url>
cd aws-resource-inspector-mcp
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure Claude Desktop:**

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
```json
{
  "mcpServers": {
    "aws-inspector": {
      "command": "python",
      "args": [
        "/full/path/to/aws-resource-inspector-mcp/src/server.py"
      ]
    }
  }
}
```

4. **Restart Claude Desktop**

## Usage Examples

In Claude Desktop, you can now ask:

- "List my EC2 instances"
- "Show me all S3 buckets"
- "What Lambda functions are running in us-west-2?"
- "What's my AWS spending this month?"
- "Find all resources tagged with Environment=production"
- "List my DynamoDB tables"
- "Show me details for table users-prod"
- "Get CPU metrics for instance i-xxxxx"
- "Show Lambda metrics for my-function"
- "What resources can I get metrics for?"

## Tools Available

### 1. list_ec2_instances
Lists EC2 instances with details (ID, type, state, tags).

**Parameters:**
- `region` (optional): AWS region (e.g., us-west-2)
  - `state` (optional): Filter by state (running, stopped, etc.)

### 2. list_s3_buckets
Lists all S3 buckets with name, region, and creation date.

### 3. list_lambda_functions
Lists Lambda functions with runtime, memory, timeout, and last modified date.

**Parameters:**
- `region` (optional): AWS region

### 4. get_cost_analysis
Gets current month's AWS costs broken down by service.

### 5. search_resources_by_tag
Searches for resources by tag key/value across EC2, S3, and Lambda.

**Parameters:**
- `tag_key` (required): Tag key to search for
  - `tag_value` (required): Tag value to match
  - `region` (optional): AWS region

### 6. list_dynamodb_tables
Lists all DynamoDB tables with basic information.

**Parameters:**
- `region` (optional): AWS region

### 7. get_dynamodb_table_details
Gets detailed information about a specific DynamoDB table.

**Parameters:**
- `table_name` (required): DynamoDB table name
- `region` (optional): AWS region

### 8. get_ec2_cpu_metrics
Gets CPU utilization metrics for an EC2 instance.

**Parameters:**
- `instance_id` (required): EC2 instance ID
- `region` (optional): AWS region
- `hours` (optional): Hours of history (default: 24, max: 168)

### 9. get_lambda_metrics
Gets invocation metrics for a Lambda function.

**Parameters:**
- `function_name` (required): Lambda function name
- `region` (optional): AWS region
- `hours` (optional): Hours of history (default: 24)

### 10. get_resource_ids
Helper tool to list resource IDs for metrics queries.

**Parameters:**
- `region` (optional): AWS region

## Project Structure
```
aws-resource-inspector-mcp/
├── src/
│   ├── server.py          # Main MCP server implementation
│   ├── tools/             # (Reserved for future tool modules)
│   ├── aws/               # (Reserved for AWS client utilities)
│   └── utils/             # (Reserved for helper functions)
├── tests/                 # (Reserved for tests)
├── requirements.txt       # Python dependencies
├── README.md
└── .gitignore
```

## IAM Permissions Required

Your AWS IAM user/role needs these permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation",
        "s3:GetBucketTagging",
        "lambda:ListFunctions",
        "lambda:ListTags",
        "ce:GetCostAndUsage",
        "dynamodb:ListTables",
        "dynamodb:DescribeTable",
        "dynamodb:DescribeContinuousBackups",
        "dynamodb:ListTagsOfResource",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

## Roadmap

### Day 2 (Planned)
- [ ] Security audit features (public S3 buckets, open security groups)
  - [ ] CloudWatch metrics integration
  - [ ] RDS database inspection
  - [ ] Response formatting improvements
  - [ ] Caching layer to reduce API calls

### Future Enhancements
- [ ] Historical cost trends
  - [ ] Resource optimization suggestions
  - [ ] Multi-account support
  - [ ] Export results to CSV/JSON

## Technical Details

- **Language**: Python 3.14
  - **MCP SDK**: mcp >= 1.0.0
  - **AWS SDK**: boto3 >= 1.34.0
  - **Protocol**: JSON-RPC 2.0 over stdio
  - **Transport**: stdin/stdout pipes

## Learning Outcomes

This project demonstrates:
- MCP server architecture and protocol
  - AWS SDK (boto3) integration
  - JSON-RPC communication
  - stdin/stdout IPC
  - Multi-region AWS resource management

## License

MIT