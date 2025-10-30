"""
Intelligent web scraping agent using LLM + MCP tools.

This agent orchestrates the MCP tools to extract structured data from web pages
according to a user-provided JSON schema. It uses an LLM to intelligently identify
CSS selectors, handle interactions, and adapt to page structure changes.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import re

from openai import OpenAI

from src.mcp_server import ToolService
from src.errors import ToolError, ErrorCode


logger = logging.getLogger(__name__)


@dataclass
class ScrapingConfig:
    """Configuration for a scraping job."""
    url: str
    schema: Dict[str, Any]
    interactions: List[Dict[str, Any]] = None
    options: Dict[str, Any] = None

    def __post_init__(self):
        if self.interactions is None:
            self.interactions = []
        if self.options is None:
            self.options = {}


@dataclass
class ExtractionResult:
    """Result of a data extraction operation."""
    status: str  # "success" or "error"
    data: Dict[str, Any]
    quality_report: Dict[str, Any]
    error: Optional[str] = None


class ScrapingAgent:
    """
    Intelligent scraping agent that uses LLM reasoning to extract structured data.

    The agent:
    1. Analyzes the target schema to understand what data to extract
    2. Navigates to the target URL and retrieves HTML
    3. Uses LLM to identify appropriate CSS selectors for each field
    4. Extracts data and converts types according to schema
    5. Handles pagination if enabled
    6. Generates quality reports
    """

    def __init__(self, openai_api_key: str, tool_service: ToolService):
        """
        Initialize the scraping agent.

        Args:
            openai_api_key: API key for OpenAI
            tool_service: MCP tool service instance
        """
        self.client = OpenAI(api_key=openai_api_key)
        self.tool_service = tool_service
        self.session_id: Optional[str] = None

    def scrape(self, config: ScrapingConfig) -> ExtractionResult:
        """
        Execute a scraping job based on the provided configuration.

        Args:
            config: Scraping configuration with URL, schema, interactions, options

        Returns:
            ExtractionResult with extracted data and quality metrics
        """
        try:
            logger.info(f"Starting scraping job for {config.url}")

            # Step 1: Navigate to URL
            session_id, nav_data = self._navigate(config.url)
            self.session_id = session_id

            # Step 2: Execute preliminary interactions (cookies, popups, etc.)
            if config.interactions:
                self._execute_interactions(config.interactions)

            # Step 3: Extract data from current page
            all_extracted_data = []
            page_count = 0
            max_pages = config.options.get("max_pages", 1)
            pagination_enabled = config.options.get("pagination", False)

            while page_count < max_pages:
                page_count += 1
                logger.info(f"Extracting data from page {page_count}")

                # Get HTML content
                _, html_data = self._call_tool("get_html", {"session_id": self.session_id})
                html_content = html_data["html"]

                # Use LLM to extract data according to schema
                page_data = self._extract_with_llm(html_content, config.schema)

                if page_data:
                    all_extracted_data.extend(page_data)

                # Handle pagination
                if pagination_enabled and page_count < max_pages:
                    has_next = self._navigate_to_next_page(html_content)
                    if not has_next:
                        logger.info("No more pages to scrape")
                        break
                else:
                    break

            # Step 4: Structure the data according to schema
            structured_data = self._structure_data(all_extracted_data, config.schema)

            # Step 5: Generate quality report
            quality_report = self._generate_quality_report(structured_data, config.schema)

            return ExtractionResult(
                status="success",
                data=structured_data,
                quality_report=quality_report
            )

        except Exception as e:
            logger.error(f"Scraping job failed: {str(e)}", exc_info=True)
            return ExtractionResult(
                status="error",
                data={},
                quality_report={},
                error=str(e)
            )

    def _navigate(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """Navigate to a URL and return session ID and navigation data."""
        session_id, data = self._call_tool("navigate", {"url": url})
        logger.info(f"Navigated to {url}, session: {session_id}")
        return session_id, data

    def _execute_interactions(self, interactions: List[Dict[str, Any]]) -> None:
        """
        Execute a list of interactions (clicks, waits, scrolls, etc.).

        Args:
            interactions: List of interaction definitions
        """
        for interaction in interactions:
            interaction_type = interaction.get("type")

            if interaction_type == "click":
                selector = interaction.get("selector")
                try:
                    self._call_tool("click", {
                        "session_id": self.session_id,
                        "selector": selector
                    })
                    logger.info(f"Clicked element: {selector}")
                except ToolError as e:
                    logger.warning(f"Click failed for {selector}: {e}")

            elif interaction_type == "wait":
                import time
                duration_ms = interaction.get("duration", 1000)
                time.sleep(duration_ms / 1000.0)
                logger.info(f"Waited {duration_ms}ms")

            elif interaction_type == "scroll":
                direction = interaction.get("direction", "bottom")
                # Note: For scrolling, we'd need to add a scroll tool or use JavaScript
                # For now, we'll log and skip
                logger.warning(f"Scroll not implemented, skipping: {direction}")

            elif interaction_type == "fill":
                selector = interaction.get("selector")
                value = interaction.get("value")
                try:
                    self._call_tool("fill", {
                        "session_id": self.session_id,
                        "selector": selector,
                        "value": value
                    })
                    logger.info(f"Filled {selector} with value")
                except ToolError as e:
                    logger.warning(f"Fill failed for {selector}: {e}")

    def _extract_with_llm(self, html_content: str, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Use LLM to analyze HTML and extract data according to schema.

        Args:
            html_content: Raw HTML of the page
            schema: Target data schema

        Returns:
            List of extracted items
        """
        # Truncate HTML if too large (keep first 50k chars for context)
        html_snippet = html_content[:50000] if len(html_content) > 50000 else html_content

        # Build the prompt for LLM
        prompt = self._build_extraction_prompt(html_snippet, schema)

        # Call OpenAI API
        response = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=4096,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Parse the response
        response_text = response.choices[0].message.content

        # Extract JSON from response
        extracted_data = self._parse_llm_response(response_text)

        return extracted_data

    def _build_extraction_prompt(self, html_snippet: str, schema: Dict[str, Any]) -> str:
        """
        Build a prompt for the LLM to extract data from HTML.

        Args:
            html_snippet: HTML content (possibly truncated)
            schema: Target data schema

        Returns:
            Formatted prompt string
        """
        schema_str = json.dumps(schema, indent=2)

        prompt = f"""You are a web scraping expert. Your task is to extract structured data from HTML according to a provided schema.

TARGET SCHEMA:
{schema_str}

HTML CONTENT:
{html_snippet}

INSTRUCTIONS:
1. Analyze the HTML to identify elements that match each field in the schema
2. Extract ALL items that match the schema structure (if it's a list of products, extract ALL products)
3. For each field, extract the appropriate data:
   - For "string" types: extract text content
   - For "number" types: extract numeric values (remove currency symbols, convert to float)
   - For "boolean" types: determine true/false based on presence/absence or text content
   - For nested objects: extract all nested fields
4. Return ONLY valid JSON matching the schema structure
5. If a field cannot be found, use null for that field
6. Ensure all extracted data is properly formatted and typed

OUTPUT FORMAT:
Return a JSON array of items matching the schema. For example, if the schema has a "produits" array, return:
{{"items": [item1, item2, ...]}}

DO NOT include explanations, markdown formatting, or any text outside the JSON.
Start your response with {{ and end with }}.
"""
        return prompt

    def _parse_llm_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse JSON from LLM response.

        Args:
            response_text: Raw text response from LLM

        Returns:
            List of extracted items
        """
        try:
            # Try to find JSON in the response
            # Look for content between first { and last }
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')

            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx + 1]
                parsed = json.loads(json_str)

                # Handle different response formats
                if isinstance(parsed, dict):
                    if "items" in parsed:
                        return parsed["items"]
                    elif any(isinstance(v, list) for v in parsed.values()):
                        # Find the first list value
                        for v in parsed.values():
                            if isinstance(v, list):
                                return v
                    else:
                        return [parsed]
                elif isinstance(parsed, list):
                    return parsed
                else:
                    return []
            else:
                logger.warning("No JSON found in LLM response")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            return []

    def _navigate_to_next_page(self, html_content: str) -> bool:
        """
        Detect and navigate to the next page in pagination.

        Args:
            html_content: Current page HTML

        Returns:
            True if successfully navigated to next page, False otherwise
        """
        # Use LLM to identify pagination button
        prompt = f"""Analyze this HTML and identify the CSS selector for the "next page" button or link.

HTML:
{html_content[:30000]}

INSTRUCTIONS:
1. Look for common pagination patterns: "Next", "Suivant", "→", page numbers, etc.
2. The button/link MUST be active and clickable (not disabled or grayed out)
3. AVOID disabled elements - look for these signs:
   - Classes like "disabled", "inactive", "current"
   - Attributes like aria-disabled="true" or disabled
   - Links without href attribute or with href="#"
4. Prefer more specific selectors that target ONLY the active next button:
   - Good: li.next:not(.disabled) a, a.next-page[href], .pagination-next:not([disabled])
   - Bad: .next, a[rel="next"]
5. Return ONLY the CSS selector, nothing else (no backticks, no markdown)
6. If no ACTIVE pagination button is found (e.g., we're on the last page), return exactly: NO_PAGINATION

Return only the selector or NO_PAGINATION:"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            max_tokens=256,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        selector = response.choices[0].message.content.strip()

        # Clean up selector - remove markdown formatting if present
        if selector.startswith("```"):
            # Extract content between ``` markers
            lines = selector.split("\n")
            # Remove first and last lines if they're markdown markers
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            selector = "\n".join(lines).strip()

        # Remove inline backticks that wrap the entire selector (e.g., `a.next`)
        if selector.startswith("`") and selector.endswith("`") and selector.count("`") == 2:
            selector = selector[1:-1].strip()

        if selector == "NO_PAGINATION" or not selector:
            return False

        logger.info(f"Attempting pagination with selector: {selector}")

        # Try to click the next button
        try:
            self._call_tool("click", {
                "session_id": self.session_id,
                "selector": selector
            })
            logger.info(f"Navigated to next page using selector: {selector}")
            # Wait for page to load
            import time
            time.sleep(2)
            return True
        except ToolError as e:
            # If element is not visible or not clickable, we're probably on the last page
            if e.code in (ErrorCode.ELEMENT_NOT_VISIBLE, ErrorCode.ELEMENT_NOT_CLICKABLE):
                logger.info(f"Pagination element not accessible ({e.code.value}) - likely on last page")
                return False
            logger.warning(f"Failed to navigate to next page: {e}")
            return False

    def _structure_data(self, extracted_items: List[Dict[str, Any]], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Structure extracted data according to the schema.

        Args:
            extracted_items: List of extracted items
            schema: Target schema

        Returns:
            Structured data matching schema format
        """
        # Find the array field in schema (e.g., "produits")
        array_field = None
        for key, value in schema.items():
            if isinstance(value, list) and len(value) > 0:
                array_field = key
                break

        if array_field:
            result = {array_field: extracted_items}
        else:
            result = {"items": extracted_items}

        # Add metadata if present in schema
        if "metadata" in schema:
            result["metadata"] = {
                "date_extraction": datetime.utcnow().isoformat() + "Z",
                "nb_resultats": len(extracted_items)
            }

        return result

    def _generate_quality_report(self, structured_data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a quality report for extracted data.

        Args:
            structured_data: Extracted and structured data
            schema: Target schema

        Returns:
            Quality report with metrics
        """
        # Find the main data array
        items = []
        for key, value in structured_data.items():
            if isinstance(value, list):
                items = value
                break

        total_items = len(items)

        if total_items == 0:
            return {
                "total_items": 0,
                "complete_items": 0,
                "completion_rate": 0.0,
                "missing_fields": [],
                "errors": []
            }

        # Analyze completeness
        complete_items = 0
        missing_fields = {}

        for item in items:
            is_complete = self._check_item_completeness(item, missing_fields)
            if is_complete:
                complete_items += 1

        completion_rate = complete_items / total_items if total_items > 0 else 0.0

        # Format missing fields report
        missing_fields_list = [
            f"{field}: {count} items"
            for field, count in missing_fields.items()
        ]

        return {
            "total_items": total_items,
            "complete_items": complete_items,
            "completion_rate": round(completion_rate, 3),
            "missing_fields": missing_fields_list,
            "errors": []
        }

    def _check_item_completeness(self, item: Dict[str, Any], missing_fields: Dict[str, int]) -> bool:
        """
        Check if an item is complete (no null/missing fields).

        Args:
            item: Item to check
            missing_fields: Dictionary to track missing field counts

        Returns:
            True if item is complete, False otherwise
        """
        is_complete = True

        def check_nested(obj: Any, prefix: str = "") -> None:
            nonlocal is_complete

            if isinstance(obj, dict):
                for key, value in obj.items():
                    field_path = f"{prefix}.{key}" if prefix else key

                    if value is None or value == "":
                        is_complete = False
                        missing_fields[field_path] = missing_fields.get(field_path, 0) + 1
                    elif isinstance(value, (dict, list)):
                        check_nested(value, field_path)
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    check_nested(item, prefix)

        check_nested(item)
        return is_complete

    def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Call an MCP tool and return the result.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tuple of (session_id, data)

        Raises:
            ToolError: If the tool call fails
        """
        result = self.tool_service.call(tool_name, arguments)

        if not result.get("ok"):
            error = result.get("error", {})
            error_code = error.get("code", "INTERNAL_ERROR")
            # Convert string to ErrorCode enum if needed
            if isinstance(error_code, str):
                try:
                    error_code = ErrorCode[error_code]
                except KeyError:
                    error_code = ErrorCode.INTERNAL_ERROR
            raise ToolError(
                code=error_code,
                message=error.get("message", "Tool call failed")
            )

        session_id = result.get("session_id")
        data = result.get("data", {})

        return session_id, data
