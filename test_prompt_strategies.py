#!/usr/bin/env python3
"""
A/B Testing Framework for Prompt Strategies

This script runs parallel batches of suburb processing using different prompt strategies,
then scores and compares the outputs to determine the optimal balance between:
- Completion rate (avoiding Azure filter rejections)
- Specificity (brand names, details, concrete references)
- Humor quality (observational comedy, wit)
- Viral potential (shareability, relatability)

Usage:
    python test_prompt_strategies.py --strategy conservative --count 10
    python test_prompt_strategies.py --strategy balanced --count 10
    python test_prompt_strategies.py --strategy aggressive --count 10
    python test_prompt_strategies.py --all --count 5  # Run all strategies with 5 suburbs each
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import statistics

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from prompt_config import PROMPT_STRATEGIES, get_search_queries, get_synthesis_prompt
from pi_coder_search.service import pi_search, pi_chat_completion


class StrategyTester:
    """Runs A/B tests on different prompt strategies."""

    def __init__(self, strategy_name: str, output_dir: str = "test_outputs"):
        self.strategy_name = strategy_name
        self.config = PROMPT_STRATEGIES.get(strategy_name)
        if not self.config:
            raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(PROMPT_STRATEGIES.keys())}")

        self.output_dir = Path(output_dir) / strategy_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: List[Dict[str, Any]] = []
        self.stats = {
            "total_suburbs": 0,
            "successful_completions": 0,
            "filter_rejections": 0,
            "other_errors": 0,
            "avg_specificity_score": 0.0,
            "avg_humor_score": 0.0,
            "avg_viral_score": 0.0,
        }

    def run_test_batch(self, suburbs: List[Dict[str, str]], max_results_per_search: int = 3) -> List[Dict[str, Any]]:
        """
        Run a test batch for a given list of suburbs.

        Args:
            suburbs: List of dicts with 'suburb', 'state', 'postcode' keys
            max_results_per_search: Reduce from default for faster testing

        Returns:
            List of result dictionaries with scores and metadata
        """
        print(f"\n{'='*60}")
        print(f"Testing Strategy: {self.strategy_name.upper()}")
        print(f"Configuration: {json.dumps(self.config, indent=2)}")
        print(f"Suburbs to process: {len(suburbs)}")
        print(f"{'='*60}\n")

        for idx, suburb_info in enumerate(suburbs, 1):
            suburb = suburb_info["suburb"]
            state = suburb_info["state"]
            postcode = suburb_info.get("postcode", "")

            print(f"[{idx}/{len(suburbs)}] Processing: {suburb}, {state} {postcode}")

            result = {
                "suburb": suburb,
                "state": state,
                "postcode": postcode,
                "strategy": self.strategy_name,
                "timestamp": datetime.now().isoformat(),
                "success": False,
                "error_type": None,
                "error_message": None,
                "search_queries_used": [],
                "search_results_count": 0,
                "synthesis_output": None,
                "scores": {
                    "specificity": 0,
                    "humor": 0,
                    "viral_potential": 0,
                    "completion": 0,
                },
                "metrics": {
                    "brand_mentions": 0,
                    "specific_details_count": 0,
                    "persona_archetypes": 0,
                    "word_count": 0,
                },
            }

            try:
                # Step 1: Generate search queries based on strategy
                search_queries = get_search_queries(suburb, state, self.strategy_name)
                result["search_queries_used"] = search_queries

                # Step 2: Execute searches (reduced results for speed)
                search_results = {}
                total_results = 0

                for query in search_queries:
                    try:
                        results = pi_search(query, max_results=max_results_per_search)
                        search_results[query] = results
                        total_results += len(results)
                        time.sleep(0.3)  # Rate limiting
                    except Exception as e:
                        print(f"  ⚠️  Search failed for query '{query[:50]}...': {str(e)}")
                        search_results[query] = []

                result["search_results_count"] = total_results

                if total_results == 0:
                    result["error_type"] = "no_search_results"
                    result["error_message"] = "No search results returned for any query"
                    self.stats["other_errors"] += 1
                    self.results.append(result)
                    continue

                # Step 3: Build synthesis prompt
                system_prompt = get_synthesis_prompt(self.strategy_name)
                user_prompt = self._build_user_prompt(suburb, state, search_results)

                # Step 4: Call LLM for synthesis
                try:
                    synthesis_response = pi_chat_completion(
                        model="gpt-4",  # Or your configured model
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.7,
                        max_tokens=2000,
                    )

                    result["synthesis_output"] = synthesis_response
                    result["success"] = True
                    self.stats["successful_completions"] += 1

                except Exception as e:
                    error_msg = str(e).lower()
                    if "content filter" in error_msg or "policy" in error_msg or "blocked" in error_msg:
                        result["error_type"] = "content_filter_rejection"
                        self.stats["filter_rejections"] += 1
                    else:
                        result["error_type"] = "api_error"
                        self.stats["other_errors"] += 1

                    result["error_message"] = str(e)
                    self.results.append(result)
                    continue

                # Step 5: Parse and score the output
                try:
                    output_data = json.loads(synthesis_response)
                    scores, metrics = self._score_output(output_data)
                    result["scores"] = scores
                    result["metrics"] = metrics

                except json.JSONDecodeError:
                    result["error_type"] = "invalid_json_output"
                    result["error_message"] = "LLM did not return valid JSON"
                    self.stats["other_errors"] += 1

                # Save individual result
                self._save_result(result)
                self.results.append(result)

                # Progress update
                print(f"  ✓ Success: {result['success']}, Scores: S={scores.get('specificity', 0)}, H={scores.get('humor', 0)}, V={scores.get('viral_potential', 0)}")

            except Exception as e:
                result["error_type"] = "unexpected_error"
                result["error_message"] = str(e)
                self.stats["other_errors"] += 1
                self.results.append(result)
                print(f"  ✗ Unexpected error: {str(e)}")

            time.sleep(0.5)  # Rate limiting between suburbs

        # Calculate aggregate stats
        self._calculate_aggregate_stats()

        return self.results

    def _build_user_prompt(self, suburb: str, state: str, search_results: Dict[str, List[Dict]]) -> str:
        """Build the user prompt with search results."""
        formatted_results = []
        for query, results in search_results.items():
            formatted_results.append(f"SEARCH QUERY: {query}")
            for i, result in enumerate(results, 1):
                formatted_results.append(f"  [{i}] {result.get('snippet', 'No snippet')} - URL: {result.get('url', 'No URL')}")
            formatted_results.append("")

        return f"""Suburb: {suburb}, {state}

SEARCH RESULTS:
{chr(10).join(formatted_results)}

Generate the JSON profile according to the system instructions."""

    def _score_output(self, output_data: Dict[str, Any]) -> tuple[Dict[str, float], Dict[str, int]]:
        """
        Score the output on multiple dimensions.

        Returns:
            Tuple of (scores dict, metrics dict)
        """
        scores = {
            "specificity": 0.0,
            "humor": 0.0,
            "viral_potential": 0.0,
            "completion": 1.0,  # If we got here, completion succeeded
        }

        metrics = {
            "brand_mentions": 0,
            "specific_details_count": 0,
            "persona_archetypes": 0,
            "word_count": 0,
        }

        # Extract text content for analysis
        all_text = ""
        personas = output_data.get("personas", [])
        metrics["persona_archetypes"] = len(personas)

        for persona in personas:
            all_text += json.dumps(persona)

        local_drama = output_data.get("local_drama", {})
        if isinstance(local_drama, dict):
            all_text += json.dumps(local_drama)

        stereotypes = output_data.get("stereotypes", [])
        if isinstance(stereotypes, list):
            all_text += " ".join(str(s) for s in stereotypes)

        # Count specific indicators
        brand_keywords = [
            "Mercedes", "BMW", "Audi", "Tesla", "Toyota", "Mazda", "Ford", "Holden",
            "Starbucks", "Campos", "Single Origin", "Flat White", "Oat Milk",
            "Lululemon", "Nike", "Adidas", "Gymshark", "Reebok",
            "Woolworths", "Coles", "Harris Farm", "Whole Foods",
            "iPhone", "Samsung", "MacBook", "AirPods",
            "Bunnings", "IKEA", "Freedom Furniture",
            "Strava", "Peloton", "CrossFit", "F45",
        ]

        for brand in brand_keywords:
            if brand.lower() in all_text.lower():
                metrics["brand_mentions"] += 1

        # Count specific details (numbers, prices, times, etc.)
        import re
        numbers = re.findall(r'\d+(?:\.\d+)?(?:km|min|hr|am|pm|\$|k|K)?', all_text)
        metrics["specific_details_count"] = len(numbers)

        # Word count
        metrics["word_count"] = len(all_text.split())

        # Scoring logic (simple heuristics)
        # Specificity: More brands + more specific details = higher score
        specificity_raw = (metrics["brand_mentions"] * 2) + (metrics["specific_details_count"] * 0.5)
        scores["specificity"] = min(10.0, specificity_raw / 2)  # Scale to 0-10

        # Humor: Harder to automate, use keyword presence and persona variety
        humor_keywords = ["ironic", "pretends", "actually", "but", "contradiction", "obsessed", "refuses", "somehow"]
        humor_count = sum(1 for kw in humor_keywords if kw in all_text.lower())
        scores["humor"] = min(10.0, (humor_count + metrics["persona_archetypes"]) / 1.5)

        # Viral potential: Combination of specificity, humor, and relatability markers
        viral_markers = ["literally", "every single", "you know the one", "if you live in", "tag your friend"]
        viral_count = sum(1 for marker in viral_markers if marker in all_text.lower())
        scores["viral_potential"] = min(10.0, (scores["specificity"] + scores["humor"]) / 2 + viral_count)

        return scores, metrics

    def _calculate_aggregate_stats(self):
        """Calculate aggregate statistics across all results."""
        if not self.results:
            return

        successful_results = [r for r in self.results if r["success"]]

        if successful_results:
            specificity_scores = [r["scores"]["specificity"] for r in successful_results]
            humor_scores = [r["scores"]["humor"] for r in successful_results]
            viral_scores = [r["scores"]["viral_potential"] for r in successful_results]

            self.stats["avg_specificity_score"] = round(statistics.mean(specificity_scores), 2)
            self.stats["avg_humor_score"] = round(statistics.mean(humor_scores), 2)
            self.stats["avg_viral_score"] = round(statistics.mean(viral_scores), 2)

        self.stats["total_suburbs"] = len(self.results)

    def _save_result(self, result: Dict[str, Any]):
        """Save individual result to file."""
        filename = f"{result['suburb']}_{result['state']}_{result['timestamp'][:19].replace(':', '-')}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    def save_summary_report(self):
        """Save a summary report of the test run."""
        report = {
            "strategy": self.strategy_name,
            "config": self.config,
            "timestamp": datetime.now().isoformat(),
            "statistics": self.stats,
            "results_summary": [
                {
                    "suburb": r["suburb"],
                    "state": r["state"],
                    "success": r["success"],
                    "error_type": r["error_type"],
                    "scores": r["scores"],
                    "metrics": r["metrics"],
                }
                for r in self.results
            ],
        }

        report_path = self.output_dir / "SUMMARY_REPORT.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n📊 Summary Report saved to: {report_path}")

    def print_summary(self):
        """Print a summary to console."""
        print(f"\n{'='*60}")
        print(f"STRATEGY TEST SUMMARY: {self.strategy_name.upper()}")
        print(f"{'='*60}")
        print(f"Total Suburbs Processed: {self.stats['total_suburbs']}")
        print(f"Successful Completions: {self.stats['successful_completions']} ({self.stats['successful_completions']/max(1,self.stats['total_suburbs'])*100:.1f}%)")
        print(f"Filter Rejections: {self.stats['filter_rejections']} ({self.stats['filter_rejections']/max(1,self.stats['total_suburbs'])*100:.1f}%)")
        print(f"Other Errors: {self.stats['other_errors']}")
        print(f"\nAverage Scores (0-10 scale):")
        print(f"  - Specificity: {self.stats['avg_specificity_score']}")
        print(f"  - Humor: {self.stats['avg_humor_score']}")
        print(f"  - Viral Potential: {self.stats['avg_viral_score']}")
        print(f"{'='*60}\n")


def load_test_suburbs(count: int) -> List[Dict[str, str]]:
    """Load a sample of suburbs for testing."""
    # Try to load from existing CSV files
    csv_files = []
    for pattern in ["*_schools.csv", "*_suburbs.csv"]:
        csv_files.extend(Path(".").glob(pattern))

    if not csv_files:
        print("⚠️  No CSV files found. Using hardcoded test suburbs.")
        test_suburbs = [
            {"suburb": "Bondi", "state": "NSW", "postcode": "2026"},
            {"suburb": "Surry Hills", "state": "NSW", "postcode": "2010"},
            {"suburb": "Paddington", "state": "NSW", "postcode": "2021"},
            {"suburb": "Newtown", "state": "NSW", "postcode": "2042"},
            {"suburb": "Manly", "state": "NSW", "postcode": "2095"},
            {"suburb": "Fortitude Valley", "state": "QLD", "postcode": "4006"},
            {"suburb": "West End", "state": "QLD", "postcode": "4101"},
            {"suburb": "New Farm", "state": "QLD", "postcode": "4005"},
            {"suburb": "Paddington", "state": "QLD", "postcode": "4064"},
            {"suburb": "Burleigh Heads", "state": "QLD", "postcode": "4220"},
        ]
        return test_suburbs[:count]

    # Load from first CSV file found
    import csv
    suburbs = []
    with open(csv_files[0], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            suburb_entry = {
                "suburb": row.get("suburb", row.get("Suburb", "")),
                "state": row.get("state", row.get("State", row.get("postcode", "")[:2])),
                "postcode": row.get("postcode", row.get("Postcode", "")),
            }
            if suburb_entry["suburb"] and suburb_entry["state"]:
                suburbs.append(suburb_entry)
            if len(suburbs) >= count:
                break

    return suburbs if suburbs else test_suburbs[:count]


def main():
    parser = argparse.ArgumentParser(description="A/B Test Prompt Strategies")
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["conservative", "balanced", "aggressive"],
        help="Strategy to test (required unless --all is used)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all strategies for comparison",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of suburbs to process per strategy (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="test_outputs",
        help="Directory to save test outputs (default: test_outputs)",
    )

    args = parser.parse_args()

    if not args.all and not args.strategy:
        print("Error: Must specify either --strategy or --all")
        parser.print_help()
        sys.exit(1)

    strategies_to_test = []
    if args.all:
        strategies_to_test = ["conservative", "balanced", "aggressive"]
    else:
        strategies_to_test = [args.strategy]

    all_results = {}

    for strategy in strategies_to_test:
        tester = StrategyTester(strategy, output_dir=args.output_dir)
        suburbs = load_test_suburbs(args.count)
        results = tester.run_test_batch(suburbs)
        tester.save_summary_report()
        tester.print_summary()
        all_results[strategy] = tester.stats

    # Print comparative summary
    if len(strategies_to_test) > 1:
        print("\n" + "="*80)
        print("COMPARATIVE SUMMARY")
        print("="*80)
        print(f"{'Strategy':<15} {'Success %':<12} {'Filter Rej %':<12} {'Specificity':<12} {'Humor':<12} {'Viral':<12}")
        print("-"*80)
        for strategy, stats in all_results.items():
            total = max(1, stats["total_suburbs"])
            success_pct = stats["successful_completions"] / total * 100
            filter_pct = stats["filter_rejections"] / total * 100
            print(f"{strategy:<15} {success_pct:<12.1f} {filter_pct:<12.1f} {stats['avg_specificity_score']:<12.2f} {stats['avg_humor_score']:<12.2f} {stats['avg_viral_score']:<12.2f}")
        print("="*80)
        print("\n💡 Recommendation: Choose the strategy with the best balance of low filter rejection rate and high viral/humor scores.")


if __name__ == "__main__":
    main()