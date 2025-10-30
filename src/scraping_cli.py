"""
Command-line interface for the intelligent scraping agent.

This allows users to run scraping jobs by providing a JSON configuration file.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from src.scraping_agent import ScrapingAgent, ScrapingConfig
from src.mcp_server import ToolService
from src.logging_conf import configure_logging


def load_config_from_file(config_path: str) -> ScrapingConfig:
    """
    Load scraping configuration from a JSON file.

    Args:
        config_path: Path to the JSON configuration file

    Returns:
        ScrapingConfig instance
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = json.load(f)

    return ScrapingConfig(
        url=config_dict.get("url"),
        schema=config_dict.get("schema"),
        interactions=config_dict.get("interactions", []),
        options=config_dict.get("options", {})
    )


def main():
    """Main CLI entry point."""

    parser = argparse.ArgumentParser(
        description="Intelligent web scraping agent using LLM + MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run scraping with a config file
  python -m src.scraping_cli --config config.json --output results.json

  # Run with custom API key
  python -m src.scraping_cli --config config.json --api-key sk-xxx --output results.json

Configuration file format:
{
  "url": "https://example.com",
  "schema": {
    "products": [
      {
        "name": "string",
        "price": "number"
      }
    ]
  },
  "interactions": [
    {"type": "click", "selector": "#accept-cookies"}
  ],
  "options": {
    "pagination": true,
    "max_pages": 5
  }
}
        """
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to JSON configuration file"
    )

    parser.add_argument(
        "--output",
        default="scraping_result.json",
        help="Output file path for results (default: scraping_result.json)"
    )

    parser.add_argument(
        "--api-key",
        help="OpenAI API key (or set OPENAI_API_KEY env var)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    configure_logging()

    # Get API key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OpenAI API key not provided", file=sys.stderr)
        print("Set OPENAI_API_KEY environment variable or use --api-key", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    try:
        config = load_config_from_file(args.config)
    except FileNotFoundError:
        print(f"ERROR: Configuration file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in configuration file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize agent
    print(f"Initializing scraping agent...", file=sys.stderr)
    tools = build_tools()
    tool_service = ToolService(tools)
    agent = ScrapingAgent(openai_api_key=api_key, tool_service=tool_service)

    # Run scraping
    print(f"Starting scraping job for: {config.url}", file=sys.stderr)
    print(f"Output will be saved to: {args.output}", file=sys.stderr)

    result = agent.scrape(config)

    # Save results
    output_data = {
        "status": result.status,
        "data": result.data,
        "quality_report": result.quality_report
    }

    if result.error:
        output_data["error"] = result.error

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Print summary
    if result.status == "success":
        print(f"\n✓ Scraping completed successfully!", file=sys.stderr)
        print(f"✓ Results saved to: {args.output}", file=sys.stderr)

        # Print summary to stderr
        total_items = result.quality_report.get("total_items", 0)
        completion_rate = result.quality_report.get("completion_rate", 0)
        print(f"\nSummary:", file=sys.stderr)
        print(f"  - Total items: {total_items}", file=sys.stderr)
        print(f"  - Completion rate: {completion_rate * 100:.1f}%", file=sys.stderr)

        sys.exit(0)
    else:
        print(f"\n✗ Scraping failed: {result.error}", file=sys.stderr)
        print(f"✗ Partial results saved to: {args.output}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
