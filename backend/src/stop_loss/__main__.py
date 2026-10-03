import argparse
import sys

from stop_loss import __version__
from stop_loss.config import get_settings
from stop_loss.logging_config import setup_logging


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser for StopLoss Intelligence."""
    parser = argparse.ArgumentParser(
        prog="python -m stop_loss",
        description="StopLoss Intelligence - Financial Intelligence Terminal & Risk Engine CLI",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        description="Available operational commands (Checkpoint 0 placeholders)",
    )

    # Ingest command
    parser_ingest = subparsers.add_parser(
        "ingest",
        help="Trigger data ingestion pipelines (weather, news, market, macro).",
        description=(
            "Trigger ingestion across one or more data providers. "
            "External ingestion will be implemented in Checkpoint 1."
        ),
    )
    parser_ingest.add_argument(
        "--provider",
        choices=["all", "weather", "news", "market", "macro"],
        default="all",
        help="Target data provider to ingest from (default: all).",
    )

    # Status command
    subparsers.add_parser(
        "status",
        help="Display current system status, configurations, and storage health.",
        description=(
            "Inspect system operational status and past ingestion runs. "
            "Live status queries will be implemented in Checkpoint 1."
        ),
    )

    # Records command
    parser_records = subparsers.add_parser(
        "records",
        help="Query and inspect stored normalized records.",
        description=(
            "Query stored intelligence records. "
            "Record querying will be implemented in Checkpoint 1."
        ),
    )
    parser_records.add_argument(
        "--type",
        choices=["weather", "news", "market_price", "macro"],
        help="Filter records by data type.",
    )
    parser_records.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of records to return (default: 10).",
    )

    return parser


def main() -> int:
    """CLI entrypoint for StopLoss Intelligence."""
    parser = build_parser()
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)

    if args.command == "ingest":
        print(f"[StopLoss CLI] Ingestion command received for provider '{args.provider}'.")
        print("[StopLoss CLI] NOTICE: External ingestion will be implemented in Checkpoint 1.")
        return 0

    if args.command == "status":
        print(f"[StopLoss CLI] StopLoss Intelligence v{__version__}")
        print(f"[StopLoss CLI] Environment: {settings.app_env}")
        print(f"[StopLoss CLI] Database Path: {settings.database_path}")
        print(f"[StopLoss CLI] Tracked Tickers: {', '.join(settings.market_tickers)}")
        print(f"[StopLoss CLI] Target Weather Location: {settings.weather_location_name}")
        print("[StopLoss CLI] NOTICE: Live database status reporting in Checkpoint 1.")
        return 0

    if args.command == "records":
        print("[StopLoss CLI] Querying normalized records...")
        print("[StopLoss CLI] NOTICE: Record querying will be implemented in Checkpoint 1.")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
