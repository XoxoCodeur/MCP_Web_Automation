"""
Demo script for Part 2: Intelligent Web Scraping Agent

This demonstrates the intelligent scraping agent that uses LLM + MCP tools
to extract structured data according to a JSON schema.
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraping_agent import ScrapingAgent, ScrapingConfig
from src.mcp_server import ToolService
from src.logging_conf import configure_logging
from dotenv import load_dotenv
load_dotenv()

def main():
    """Run the Part 2 demo scenario."""

    # Setup logging
    configure_logging()
    logger = logging.getLogger(__name__)

    print("=" * 80)
    print("Part 2 Demo: Intelligent Web Scraping Agent")
    print("=" * 80)
    print()

    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("Please set it with: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    # Initialize tool service
    tool_service = ToolService()

    # Initialize scraping agent
    agent = ScrapingAgent(
        openai_api_key=api_key,
        tool_service=tool_service
    )

    print("Demo 2: Extract book information")
    print("-" * 80)

    config = ScrapingConfig(
        url="https://books.toscrape.com/",
        schema={
            "books": [
                {
                    "title": "string",
                    "price": "number",
                    "availability": "string",
                    "rating": "string"
                }
            ],
            "metadata": {
                "date_extraction": "datetime",
                "nb_resultats": "number"
            }
        },
        interactions=[],
        options={
            "pagination": True,
            "max_pages": 2
        }
    )

    print(f"\nTarget URL: {config.url}")
    print(f"Schema: {json.dumps(config.schema, indent=2)}")
    print("\nExtracting data...")

    result = agent.scrape(config)

    if result.status == "success":
        print(f"\n✓ Extraction successful!")
        print(f"\nExtracted data (first 3 items):")
        data_preview = result.data.copy()
        if "products" in data_preview and len(data_preview["products"]) > 3:
            data_preview["products"] = data_preview["products"][:3]
            data_preview["_note"] = f"Showing 3 of {len(result.data['products'])} items"
        print(json.dumps(data_preview, indent=2, ensure_ascii=False))
        print(f"\nQuality report:")
        print(json.dumps(result.quality_report, indent=2))

        # Save result
        output_file = Path(__file__).parent / "result_demo2.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "status": result.status,
                "data": result.data,
                "quality_report": result.quality_report
            }, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Saved result to: {output_file}")
    else:
        print(f"\n✗ Extraction failed: {result.error}")

    print("\n" + "=" * 80)
    print("Demo completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()
