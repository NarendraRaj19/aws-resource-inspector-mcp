"""Output formatting utilities for better readability."""


def format_table(headers: list[str], rows: list[list], title: str = None) -> str:
    """Format data as a simple text table."""
    if not rows:
        return "No data to display"

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build the table
    result = []

    # Add title if provided
    if title:
        result.append(f"\n{title}")
        result.append("=" * sum(col_widths + [3 * (len(headers) - 1)]))
        result.append("")

    # Header row
    header_row = " │ ".join(
        headers[i].ljust(col_widths[i]) for i in range(len(headers))
    )
    result.append(header_row)

    # Separator
    separator = "─┼─".join("─" * w for w in col_widths)
    result.append(separator)

    # Data rows
    for row in rows:
        data_row = " │ ".join(
            str(row[i]).ljust(col_widths[i]) for i in range(len(row))
        )
        result.append(data_row)

    return "\n".join(result)


def format_cost(amount: float) -> str:
    """Format cost with currency symbol."""
    return f"${amount:.2f}"


def format_bytes(bytes_value: int) -> str:
    """Format bytes in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def format_timestamp(timestamp) -> str:
    """Format timestamp to readable string."""
    if hasattr(timestamp, 'strftime'):
        return timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    return str(timestamp)


def status_indicator(status: str) -> str:
    """Add visual indicator based on status."""
    status_lower = status.lower()

    if status_lower in ['running', 'active', 'enabled', 'available', 'healthy']:
        return f"✅ {status}"
    elif status_lower in ['stopped', 'disabled', 'terminated', 'deleting']:
        return f"⚠️  {status}"
    elif status_lower in ['error', 'failed', 'unhealthy']:
        return f"❌ {status}"
    else:
        return status


def format_summary(title: str, stats: dict) -> str:
    """Format summary statistics."""
    result = [f"\n{title}", "=" * len(title), ""]

    for key, value in stats.items():
        result.append(f"{key}: {value}")

    return "\n".join(result)