#!/usr/bin/env python3
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from utils.formatters import format_table, status_indicator, format_timestamp
from utils.formatters import format_cost, format_summary

# Initialize MCP server
app = Server("aws-resource-inspector")


# AWS clients will be initialized per-region as needed
def get_aws_client(service: str, region: str = None):
    """Get AWS client for a specific service and region."""
    try:
        if region:
            return boto3.client(service, region_name=region)
        return boto3.client(service)
    except NoCredentialsError:
        raise Exception("AWS credentials not configured. Run 'aws configure' first.")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="list_ec2_instances",
            description="List all EC2 instances in a region with their details (ID, type, state, tags)",
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "AWS region (e.g., us-west-2). If not specified, uses default region.",
                    },
                    "state": {
                        "type": "string",
                        "description": "Filter by instance state (running, stopped, terminated, etc.)",
                    }
                },
            },
        ),
        Tool(
            name="list_s3_buckets",
            description="List all S3 buckets with their details (name, region, creation date)",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="list_lambda_functions",
            description="List all Lambda functions with their details (name, runtime, memory, timeout, last modified)",
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "AWS region (e.g., us-west-2). If not specified, uses default region.",
                    },
                },
            },
        ),
        Tool(
            name="get_cost_analysis",
            description="Get AWS costs for the current month, broken down by service. Shows total costs and top spending services.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="search_resources_by_tag",
            description="Search for AWS resources (EC2, S3, Lambda) by tag key and value. Useful for finding all resources in a project or environment.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag_key": {
                        "type": "string",
                        "description": "Tag key to search for (e.g., 'Environment', 'Project', 'Owner')",
                    },
                    "tag_value": {
                        "type": "string",
                        "description": "Tag value to match (e.g., 'production', 'website', 'john')",
                    },
                    "region": {
                        "type": "string",
                        "description": "AWS region to search in. If not specified, uses default region.",
                    },
                },
                "required": ["tag_key", "tag_value"],
            },
        ),
        Tool(
            name="get_ec2_cpu_metrics",
            description="Get CPU utilization metrics for EC2 instances over a specified time period. Shows average, maximum, and minimum CPU usage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "instance_id": {
                        "type": "string",
                        "description": "EC2 instance ID (e.g., i-1234567890abcdef0)",
                    },
                    "region": {
                        "type": "string",
                        "description": "AWS region. If not specified, uses default region.",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours of historical data to retrieve (default: 24, max: 168 for 7 days)",
                    },
                },
                "required": ["instance_id"],
            },
        ),
        Tool(
            name="get_lambda_metrics",
            description="Get invocation metrics for a Lambda function. Shows invocation count, errors, duration, and throttles over a specified time period.",
            inputSchema={
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Lambda function name",
                    },
                    "region": {
                        "type": "string",
                        "description": "AWS region. If not specified, uses default region.",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours of historical data to retrieve (default: 24)",
                    },
                },
                "required": ["function_name"],
            },
        ),
        Tool(
            name="list_dynamodb_tables",
            description="List all DynamoDB tables with their basic information (name, status, item count, size).",
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "AWS region. If not specified, uses default region.",
                    },
                },
            },
        ),
        Tool(
            name="get_dynamodb_table_details",
            description="Get detailed information about a specific DynamoDB table including schema, indexes, capacity, and metrics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "DynamoDB table name",
                    },
                    "region": {
                        "type": "string",
                        "description": "AWS region. If not specified, uses default region.",
                    },
                },
                "required": ["table_name"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "list_ec2_instances":
            return await list_ec2_instances(arguments)
        elif name == "list_s3_buckets":
            return await list_s3_buckets(arguments)
        elif name == "list_lambda_functions":
            return await list_lambda_functions(arguments)
        elif name == "get_cost_analysis":
            return await get_cost_analysis(arguments)
        elif name == "search_resources_by_tag":
            return await search_resources_by_tag(arguments)
        elif name == "get_ec2_cpu_metrics":
            return await get_ec2_cpu_metrics(arguments)
        elif name == "get_lambda_metrics":
            return await get_lambda_metrics(arguments)
        elif name == "list_dynamodb_tables":
            return await list_dynamodb_tables(arguments)
        elif name == "get_dynamodb_table_details":
            return await get_dynamodb_table_details(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    except ClientError as e:
        error_msg = f"AWS API Error: {e.response['Error']['Message']}"
        return [TextContent(type="text", text=error_msg)]
    except NoCredentialsError:
        return [TextContent(type="text", text="AWS credentials not configured. Run 'aws configure'.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def list_ec2_instances(arguments: dict) -> list[TextContent]:
    """List EC2 instances."""
    region = arguments.get("region")
    state_filter = arguments.get("state")

    ec2 = get_aws_client("ec2", region)

    # Build filters
    filters = []
    if state_filter:
        filters.append({"Name": "instance-state-name", "Values": [state_filter]})

    # Describe instances
    if filters:
        response = ec2.describe_instances(Filters=filters)
    else:
        response = ec2.describe_instances()

    # Format as table
    headers = ["Instance ID", "Name", "Type", "State", "AZ", "Private IP", "Public IP"]
    rows = []

    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            # Get instance name from tags
            name = "N/A"
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break

            rows.append([
                instance["InstanceId"],
                name,
                instance["InstanceType"],
                status_indicator(instance["State"]["Name"]),
                instance["Placement"]["AvailabilityZone"],
                instance.get("PrivateIpAddress", "N/A"),
                instance.get("PublicIpAddress", "N/A"),
            ])

    if not rows:
        result = f"No EC2 instances found in region {region or 'default'}."
    else:
        title = f"EC2 Instances in {region or 'default region'} ({len(rows)} found)"
        result = format_table(headers, rows, title)

    return [TextContent(type="text", text=result)]


async def list_s3_buckets(arguments: dict) -> list[TextContent]:
    """List S3 buckets."""
    s3 = get_aws_client("s3")

    # List buckets
    response = s3.list_buckets()

    headers = ["Bucket Name", "Region", "Created"]
    rows = []

    for bucket in response["Buckets"]:
        bucket_name = bucket["Name"]

        # Get bucket region
        try:
            location = s3.get_bucket_location(Bucket=bucket_name)
            region = location["LocationConstraint"] or "us-east-1"
        except ClientError:
            region = "Unknown"

        rows.append([
            bucket_name,
            region,
            format_timestamp(bucket["CreationDate"]),
        ])

    if not rows:
        result = "No S3 buckets found."
    else:
        title = f"S3 Buckets ({len(rows)} found)"
        result = format_table(headers, rows, title)

    return [TextContent(type="text", text=result)]


async def list_lambda_functions(arguments: dict) -> list[TextContent]:
    """List Lambda functions."""
    region = arguments.get("region")

    lambda_client = get_aws_client("lambda", region)

    # List functions
    headers = ["Function Name", "Runtime", "Memory (MB)", "Timeout (s)", "Last Modified"]
    rows = []

    paginator = lambda_client.get_paginator('list_functions')

    for page in paginator.paginate():
        for func in page['Functions']:
            rows.append([
                func["FunctionName"],
                func.get("Runtime", "N/A"),
                func["MemorySize"],
                func["Timeout"],
                format_timestamp(func["LastModified"]),
            ])

    if not rows:
        result = f"No Lambda functions found in region {region or 'default'}."
    else:
        title = f"Lambda Functions in {region or 'default region'} ({len(rows)} found)"
        result = format_table(headers, rows, title)

    return [TextContent(type="text", text=result)]


async def get_cost_analysis(arguments: dict) -> list[TextContent]:
    """Get current month's AWS costs."""
    from datetime import datetime

    ce = get_aws_client("ce", "us-east-1")  # Cost Explorer is only in us-east-1

    # Get current month's date range
    today = datetime.now()
    start_of_month = today.replace(day=1).strftime('%Y-%m-%d')
    end_of_today = today.strftime('%Y-%m-%d')

    try:
        # Get costs grouped by service
        response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start_of_month,
                'End': end_of_today
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ]
        )

        # Parse results
        headers = ["Service", "Cost"]
        rows = []
        total_cost = 0

        if response['ResultsByTime']:
            for group in response['ResultsByTime'][0]['Groups']:
                service = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])

                if amount > 0.01:  # Only show services with meaningful costs
                    rows.append([
                        service,
                        format_cost(amount)
                    ])
                    total_cost += amount

        # Sort by cost (extract numeric value for sorting)
        rows.sort(key=lambda x: float(x[1].replace('$', '')), reverse=True)

        if not rows:
            result = "No costs found for the current month."
        else:
            summary_stats = {
                "Period": f"{start_of_month} to {end_of_today}",
                "Total Cost": format_cost(total_cost),
                "Services": len(rows)
            }

            result = format_summary("AWS Cost Analysis", summary_stats)
            result += "\n\n"
            result += format_table(headers, rows[:10], "Top 10 Services by Cost")  # Limit to top 10

        return [TextContent(type="text", text=result)]

    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDeniedException':
            return [TextContent(
                type="text",
                text="Cost Explorer access denied. You need 'ce:GetCostAndUsage' permission or enable Cost Explorer in AWS console."
            )]
        raise

async def search_resources_by_tag(arguments: dict) -> list[TextContent]:
    """Search resources by tag."""
    tag_key = arguments.get("tag_key")
    tag_value = arguments.get("tag_value")
    region = arguments.get("region")

    results = {
        "EC2 Instances": [],
        "S3 Buckets": [],
        "Lambda Functions": []
    }

    # Search EC2 instances
    ec2 = get_aws_client("ec2", region)
    ec2_response = ec2.describe_instances(
        Filters=[
            {"Name": f"tag:{tag_key}", "Values": [tag_value]}
        ]
    )

    for reservation in ec2_response["Reservations"]:
        for instance in reservation["Instances"]:
            name = "N/A"
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break

            results["EC2 Instances"].append({
                "InstanceId": instance["InstanceId"],
                "Name": name,
                "State": instance["State"]["Name"],
                "InstanceType": instance["InstanceType"]
            })

    # Search S3 buckets (S3 tags require separate API calls per bucket)
    s3 = get_aws_client("s3")
    buckets_response = s3.list_buckets()

    for bucket in buckets_response["Buckets"]:
        bucket_name = bucket["Name"]
        try:
            tags_response = s3.get_bucket_tagging(Bucket=bucket_name)
            for tag in tags_response.get("TagSet", []):
                if tag["Key"] == tag_key and tag["Value"] == tag_value:
                    results["S3 Buckets"].append({
                        "Name": bucket_name,
                        "CreationDate": bucket["CreationDate"].isoformat()
                    })
                    break
        except ClientError as e:
            # Bucket might not have tags
            if e.response['Error']['Code'] != 'NoSuchTagSet':
                pass

    # Search Lambda functions
    lambda_client = get_aws_client("lambda", region)
    lambda_response = lambda_client.list_functions()

    for func in lambda_response["Functions"]:
        func_arn = func["FunctionArn"]
        try:
            tags_response = lambda_client.list_tags(Resource=func_arn)
            tags = tags_response.get("Tags", {})
            if tags.get(tag_key) == tag_value:
                results["Lambda Functions"].append({
                    "FunctionName": func["FunctionName"],
                    "Runtime": func.get("Runtime", "N/A"),
                    "LastModified": func["LastModified"]
                })
        except ClientError:
            pass

    # Format results
    total_found = sum(len(v) for v in results.values())

    if total_found == 0:
        result = f"No resources found with tag {tag_key}={tag_value}"
    else:
        result = f"Found {total_found} resource(s) with tag {tag_key}={tag_value}:\n\n"
        result += json.dumps(results, indent=2)

    return [TextContent(type="text", text=result)]

async def get_ec2_cpu_metrics(arguments: dict) -> list[TextContent]:
    """Get CPU utilization metrics for an EC2 instance."""
    from datetime import datetime, timedelta

    instance_id = arguments.get("instance_id")
    region = arguments.get("region")
    hours = arguments.get("hours", 24)

    # Limit to 7 days
    if hours > 168:
        hours = 168

    cloudwatch = get_aws_client("cloudwatch", region)

    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    try:
        # Get CPU utilization metrics
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[
                {
                    'Name': 'InstanceId',
                    'Value': instance_id
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # 1 hour intervals
            Statistics=['Average', 'Maximum', 'Minimum']
        )

        if not response['Datapoints']:
            return [TextContent(
                type="text",
                text=f"No CPU metrics found for instance {instance_id} in the last {hours} hours. Instance may be stopped or metrics not available yet."
            )]

        # Sort by timestamp
        datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])

        # Calculate overall statistics
        avg_cpu = sum(d['Average'] for d in datapoints) / len(datapoints)
        max_cpu = max(d['Maximum'] for d in datapoints)
        min_cpu = min(d['Minimum'] for d in datapoints)

        result = f"EC2 CPU Metrics for {instance_id}\n"
        result += f"{'=' * 50}\n\n"
        result += f"Time Range: Last {hours} hours\n"
        result += f"Data Points: {len(datapoints)}\n\n"
        result += f"Overall Statistics:\n"
        result += f"  Average CPU: {avg_cpu:.2f}%\n"
        result += f"  Maximum CPU: {max_cpu:.2f}%\n"
        result += f"  Minimum CPU: {min_cpu:.2f}%\n\n"

        # Show recent data points
        result += f"Recent CPU Usage (hourly):\n\n"

        for dp in datapoints[-24:]:  # Last 24 data points
            timestamp = dp['Timestamp'].strftime('%Y-%m-%d %H:%M UTC')
            avg = dp['Average']
            result += f"  {timestamp}: {avg:.2f}% (max: {dp['Maximum']:.2f}%, min: {dp['Minimum']:.2f}%)\n"

        return [TextContent(type="text", text=result)]

    except ClientError as e:
        return [TextContent(
            type="text",
            text=f"Error getting metrics: {e.response['Error']['Message']}"
        )]


async def get_lambda_metrics(arguments: dict) -> list[TextContent]:
    """Get metrics for a Lambda function."""
    from datetime import datetime, timedelta

    function_name = arguments.get("function_name")
    region = arguments.get("region")
    hours = arguments.get("hours", 24)

    cloudwatch = get_aws_client("cloudwatch", region)

    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    metrics_to_fetch = [
        ('Invocations', 'Sum'),
        ('Errors', 'Sum'),
        ('Duration', 'Average'),
        ('Throttles', 'Sum'),
        ('ConcurrentExecutions', 'Maximum')
    ]

    results = {}

    for metric_name, stat in metrics_to_fetch:
        try:
            response = cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'FunctionName',
                        'Value': function_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour intervals
                Statistics=[stat]
            )

            if response['Datapoints']:
                datapoints = sorted(response['Datapoints'], key=lambda x: x['Timestamp'])
                results[metric_name] = {
                    'datapoints': datapoints,
                    'stat': stat
                }
        except ClientError:
            pass

    if not results:
        return [TextContent(
            type="text",
            text=f"No metrics found for Lambda function '{function_name}' in the last {hours} hours."
        )]

    # Build result
    result = f"Lambda Metrics for {function_name}\n"
    result += f"{'=' * 50}\n\n"
    result += f"Time Range: Last {hours} hours\n\n"

    # Summary statistics
    if 'Invocations' in results:
        total_invocations = sum(d['Sum'] for d in results['Invocations']['datapoints'])
        result += f"Total Invocations: {int(total_invocations)}\n"

    if 'Errors' in results:
        total_errors = sum(d['Sum'] for d in results['Errors']['datapoints'])
        result += f"Total Errors: {int(total_errors)}\n"

        if 'Invocations' in results and total_invocations > 0:
            error_rate = (total_errors / total_invocations) * 100
            result += f"Error Rate: {error_rate:.2f}%\n"

    if 'Duration' in results:
        avg_duration = sum(d['Average'] for d in results['Duration']['datapoints']) / len(
            results['Duration']['datapoints'])
        result += f"Average Duration: {avg_duration:.2f} ms\n"

    if 'Throttles' in results:
        total_throttles = sum(d['Sum'] for d in results['Throttles']['datapoints'])
        result += f"Total Throttles: {int(total_throttles)}\n"

    if 'ConcurrentExecutions' in results:
        max_concurrent = max(d['Maximum'] for d in results['ConcurrentExecutions']['datapoints'])
        result += f"Max Concurrent Executions: {int(max_concurrent)}\n"

    result += f"\n{'=' * 50}\n"
    result += "\nHourly Breakdown:\n\n"

    # Show invocations per hour
    if 'Invocations' in results:
        for dp in results['Invocations']['datapoints'][-24:]:
            timestamp = dp['Timestamp'].strftime('%Y-%m-%d %H:%M UTC')
            invocations = int(dp['Sum'])
            result += f"  {timestamp}: {invocations} invocations\n"

    return [TextContent(type="text", text=result)]

async def list_dynamodb_tables(arguments: dict) -> list[TextContent]:
    """List DynamoDB tables."""
    region = arguments.get("region")

    dynamodb = get_aws_client("dynamodb", region)

    # List tables
    try:
        response = dynamodb.list_tables()
        table_names = response.get('TableNames', [])

        if not table_names:
            return [TextContent(
                type="text",
                text=f"No DynamoDB tables found in region {region or 'default'}."
            )]

        # Get details for each table
        headers = ["Table Name", "Status", "Item Count", "Table Size", "Billing Mode"]
        rows = []

        for table_name in table_names:
            try:
                table_info = dynamodb.describe_table(TableName=table_name)
                table = table_info['Table']

                rows.append([
                    table['TableName'],
                    status_indicator(table['TableStatus']),
                    f"{table.get('ItemCount', 0):,}",
                    format_bytes(table.get('TableSizeBytes', 0)),
                    table.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED'),
                ])
            except ClientError as e:
                rows.append([
                    table_name,
                    f"❌ Error: {e.response['Error']['Code']}",
                    "N/A",
                    "N/A",
                    "N/A",
                ])

        title = f"DynamoDB Tables in {region or 'default region'} ({len(rows)} found)"
        result = format_table(headers, rows, title)

        return [TextContent(type="text", text=result)]

    except ClientError as e:
        return [TextContent(
            type="text",
            text=f"Error listing DynamoDB tables: {e.response['Error']['Message']}"
        )]


async def get_dynamodb_table_details(arguments: dict) -> list[TextContent]:
    """Get detailed information about a DynamoDB table."""
    table_name = arguments.get("table_name")
    region = arguments.get("region")

    dynamodb = get_aws_client("dynamodb", region)

    try:
        response = dynamodb.describe_table(TableName=table_name)
        table = response['Table']

        result = f"\nDynamoDB Table Details: {table_name}\n"
        result += "=" * 60 + "\n\n"

        # Basic Info
        result += "Basic Information:\n"
        result += f"  Status: {status_indicator(table['TableStatus'])}\n"
        result += f"  Creation Date: {format_timestamp(table['CreationDateTime'])}\n"
        result += f"  Item Count: {table.get('ItemCount', 0):,}\n"
        result += f"  Table Size: {format_bytes(table.get('TableSizeBytes', 0))}\n"
        result += f"  Table ARN: {table['TableArn']}\n\n"

        # Billing Mode
        billing_mode = table.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED')
        result += f"Billing Mode: {billing_mode}\n"

        if billing_mode == 'PROVISIONED':
            provisioned = table.get('ProvisionedThroughput', {})
            result += f"  Read Capacity: {provisioned.get('ReadCapacityUnits', 0)} RCU\n"
            result += f"  Write Capacity: {provisioned.get('WriteCapacityUnits', 0)} WCU\n"
        result += "\n"

        # Key Schema
        result += "Key Schema:\n"
        for key in table['KeySchema']:
            key_type = "Partition Key" if key['KeyType'] == 'HASH' else "Sort Key"

            # Find attribute type
            attr_type = "Unknown"
            for attr in table['AttributeDefinitions']:
                if attr['AttributeName'] == key['AttributeName']:
                    attr_type = attr['AttributeType']
                    break

            result += f"  {key_type}: {key['AttributeName']} ({attr_type})\n"
        result += "\n"

        # Global Secondary Indexes
        gsi = table.get('GlobalSecondaryIndexes', [])
        if gsi:
            result += f"Global Secondary Indexes ({len(gsi)}):\n"
            for index in gsi:
                result += f"  • {index['IndexName']}\n"
                result += f"    Status: {status_indicator(index['IndexStatus'])}\n"
                result += f"    Item Count: {index.get('ItemCount', 0):,}\n"

                if billing_mode == 'PROVISIONED':
                    idx_provisioned = index.get('ProvisionedThroughput', {})
                    result += f"    Read Capacity: {idx_provisioned.get('ReadCapacityUnits', 0)} RCU\n"
                    result += f"    Write Capacity: {idx_provisioned.get('WriteCapacityUnits', 0)} WCU\n"
            result += "\n"

        # Local Secondary Indexes
        lsi = table.get('LocalSecondaryIndexes', [])
        if lsi:
            result += f"Local Secondary Indexes ({len(lsi)}):\n"
            for index in lsi:
                result += f"  • {index['IndexName']}\n"
                result += f"    Item Count: {index.get('ItemCount', 0):,}\n"
            result += "\n"

        # Stream Specification
        stream = table.get('StreamSpecification')
        if stream and stream.get('StreamEnabled'):
            result += "DynamoDB Streams:\n"
            result += f"  Enabled: ✅ Yes\n"
            result += f"  View Type: {stream.get('StreamViewType', 'N/A')}\n"
            result += f"  Stream ARN: {table.get('LatestStreamArn', 'N/A')}\n\n"

        # Encryption
        sse = table.get('SSEDescription')
        if sse:
            result += "Encryption:\n"
            result += f"  Status: {status_indicator(sse.get('Status', 'UNKNOWN'))}\n"
            result += f"  Type: {sse.get('SSEType', 'N/A')}\n\n"

        # Point-in-time Recovery
        try:
            pitr_response = dynamodb.describe_continuous_backups(TableName=table_name)
            pitr_status = pitr_response['ContinuousBackupsDescription']['PointInTimeRecoveryDescription'][
                'PointInTimeRecoveryStatus']
            result += "Point-in-Time Recovery:\n"
            result += f"  Status: {status_indicator(pitr_status)}\n\n"
        except ClientError:
            pass

        # Tags
        try:
            tags_response = dynamodb.list_tags_of_resource(ResourceArn=table['TableArn'])
            tags = tags_response.get('Tags', [])
            if tags:
                result += f"Tags ({len(tags)}):\n"
                for tag in tags:
                    result += f"  {tag['Key']}: {tag['Value']}\n"
                result += "\n"
        except ClientError:
            pass

        return [TextContent(type="text", text=result)]

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            return [TextContent(
                type="text",
                text=f"Table '{table_name}' not found in region {region or 'default'}."
            )]
        return [TextContent(
            type="text",
            text=f"Error getting table details: {e.response['Error']['Message']}"
        )]

async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())