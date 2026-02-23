#!/usr/bin/env python3
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

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

    # Format response
    instances = []
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            # Get instance name from tags
            name = "N/A"
            for tag in instance.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break

            instances.append({
                "InstanceId": instance["InstanceId"],
                "Name": name,
                "InstanceType": instance["InstanceType"],
                "State": instance["State"]["Name"],
                "LaunchTime": instance["LaunchTime"].isoformat(),
                "AvailabilityZone": instance["Placement"]["AvailabilityZone"],
                "PrivateIpAddress": instance.get("PrivateIpAddress", "N/A"),
                "PublicIpAddress": instance.get("PublicIpAddress", "N/A"),
            })

    if not instances:
        result = f"No EC2 instances found in region {region or 'default'}."
    else:
        result = f"Found {len(instances)} EC2 instance(s):\n\n"
        result += json.dumps(instances, indent=2)

    return [TextContent(type="text", text=result)]


async def list_s3_buckets(arguments: dict) -> list[TextContent]:
    """List S3 buckets."""
    s3 = get_aws_client("s3")

    # List buckets
    response = s3.list_buckets()

    buckets = []
    for bucket in response["Buckets"]:
        bucket_name = bucket["Name"]

        # Get bucket region
        try:
            location = s3.get_bucket_location(Bucket=bucket_name)
            region = location["LocationConstraint"] or "us-east-1"
        except ClientError:
            region = "Unknown"

        buckets.append({
            "Name": bucket_name,
            "CreationDate": bucket["CreationDate"].isoformat(),
            "Region": region,
        })

    if not buckets:
        result = "No S3 buckets found."
    else:
        result = f"Found {len(buckets)} S3 bucket(s):\n\n"
        result += json.dumps(buckets, indent=2)

    return [TextContent(type="text", text=result)]


async def list_lambda_functions(arguments: dict) -> list[TextContent]:
    """List Lambda functions."""
    region = arguments.get("region")

    lambda_client = get_aws_client("lambda", region)

    # List functions
    functions = []
    paginator = lambda_client.get_paginator('list_functions')

    for page in paginator.paginate():
        for func in page['Functions']:
            functions.append({
                "FunctionName": func["FunctionName"],
                "Runtime": func.get("Runtime", "N/A"),
                "MemorySize": func["MemorySize"],
                "Timeout": func["Timeout"],
                "LastModified": func["LastModified"],
                "CodeSize": func["CodeSize"],
                "Handler": func["Handler"],
                "Description": func.get("Description", "N/A"),
            })

    if not functions:
        result = f"No Lambda functions found in region {region or 'default'}."
    else:
        result = f"Found {len(functions)} Lambda function(s):\n\n"
        result += json.dumps(functions, indent=2)

    return [TextContent(type="text", text=result)]


async def get_cost_analysis(arguments: dict) -> list[TextContent]:
    """Get current month's AWS costs."""
    from datetime import datetime, timedelta

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
        costs = []
        total_cost = 0

        if response['ResultsByTime']:
            for group in response['ResultsByTime'][0]['Groups']:
                service = group['Keys'][0]
                amount = float(group['Metrics']['UnblendedCost']['Amount'])

                if amount > 0.01:  # Only show services with meaningful costs
                    costs.append({
                        "Service": service,
                        "Cost": f"${amount:.2f}",
                        "Amount": amount
                    })
                    total_cost += amount

        # Sort by cost (highest first)
        costs.sort(key=lambda x: x['Amount'], reverse=True)

        # Remove the Amount field (only used for sorting)
        for cost in costs:
            del cost['Amount']

        if not costs:
            result = "No costs found for the current month."
        else:
            result = f"AWS Costs for {start_of_month} to {end_of_today}\n"
            result += f"Total: ${total_cost:.2f}\n\n"
            result += f"Top {min(10, len(costs))} Services:\n\n"
            result += json.dumps(costs[:10], indent=2)

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


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())