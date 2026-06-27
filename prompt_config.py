#!/usr/bin/env python3
"""
Configurable prompt strategies for different risk tolerances.
Allows switching between conservative, balanced, and aggressive content generation.
"""

PROMPT_STRATEGIES = {
    "conservative": {
        "name": "Conservative",
        "description": "Safe, gentle humor. Lowest risk of filter triggers.",
        "search_terms": [
            "what is it like living in",
            "suburb profile",
            "family friendly activities",
        ],
        "synthesis_tone": "lighthearted, gentle humor, affectionate observations",
        "avoid_topics": ["politics", "controversy", "negative stereotypes", "complaints"],
        "encourage_topics": ["community vibes", "local amenities", "lifestyle perks"],
        "max_results_per_query": 5,
        "edge_level": "low",
    },
    "balanced": {
        "name": "Balanced",
        "description": "Observational comedy with affectionate roasting. Good for viral potential.",
        "search_terms": [
            "reputation",
            "type of people live in",
            "lifestyle",
            "complaints",
            "house prices",
        ],
        "synthesis_tone": "observational comedy, affectionate roasting, larrikin spirit",
        "avoid_topics": ["race", "religion", "sexuality", "genuine hardship", "crime"],
        "encourage_topics": [
            "class markers",
            "consumption patterns",
            "petty dramas",
            "pretensions",
        ],
        "max_results_per_query": 8,
        "edge_level": "medium",
    },
    "aggressive": {
        "name": "Aggressive",
        "description": "Sharp satire and social commentary. Higher viral potential, higher filter risk.",
        "search_terms": [
            "controversy",
            "problem",
            "complaint",
            "gentrification",
            "reputation",
            "what's wrong with",
            "annoying things about",
        ],
        "synthesis_tone": "sharp satire, social commentary, punchy humor, brutal honesty",
        "avoid_topics": [
            "protected attributes",
            "illegal activities",
            "genuine trauma",
            "violence",
        ],
        "encourage_topics": [
            "hypocrisy",
            "pretension",
            "absurdity",
            "specific brand mentions",
            "class warfare",
        ],
        "max_results_per_query": 10,
        "edge_level": "high",
    },
}


def get_search_queries(
    suburb: str, state: str, strategy: str = "balanced"
) -> list[dict]:
    """
    Generate search queries based on the selected strategy.

    Args:
        suburb: Suburb name (e.g., "Bondi")
        state: State abbreviation (e.g., "NSW")
        strategy: One of "conservative", "balanced", "aggressive"

    Returns:
        List of dicts with 'category' and 'query' keys
    """
    if strategy not in PROMPT_STRATEGIES:
        raise ValueError(
            f"Invalid strategy '{strategy}'. Must be one of: {list(PROMPT_STRATEGIES.keys())}"
        )

    config = PROMPT_STRATEGIES[strategy]
    reddit_sub = "sydney" if state == "NSW" else "brisbane"

    queries = []

    # Core reputation/vibe query (all strategies)
    queries.append(
        {
            "category": "vibe",
            "query": f'site:reddit.com/r/{reddit_sub} "{suburb}" {config["search_terms"][0]}',
        }
    )

    # People/reputation query
    if len(config["search_terms"]) > 1:
        queries.append(
            {
                "category": "reputation",
                "query": f'"{suburb}" {config["search_terms"][1]} suburb profile',
            }
        )

    # Lifestyle query (balanced/aggressive)
    if "lifestyle" in config["search_terms"] or len(config["search_terms"]) > 2:
        queries.append(
            {
                "category": "lifestyle",
                "query": f'"{suburb}" coffee shops restaurants weekend activities lifestyle',
            }
        )

    # Complaints query (balanced/aggressive)
    if "complaints" in config["search_terms"] or "complaint" in config["search_terms"]:
        queries.append(
            {
                "category": "complaints",
                "query": f'"{suburb}" complaint problem issue annoying',
            }
        )

    # Class markers/housing query (balanced/aggressive)
    if "house prices" in config["search_terms"] or "gentrification" in config[
        "search_terms"
    ]:
        queries.append(
            {
                "category": "class_markers",
                "query": f'"{suburb}" house prices rent expensive affordable gentrification',
            }
        )

    # Extra aggressive queries
    if strategy == "aggressive":
        if "controversy" in config["search_terms"]:
            queries.append(
                {
                    "category": "controversy",
                    "query": f'"{suburb}" controversy scandal dispute',
                }
            )
        if "what's wrong with" in config["search_terms"]:
            queries.append(
                {
                    "category": "criticism",
                    "query": f'"{suburb}" "what\'s wrong with" worst thing about',
                }
            )

    return queries


def get_synthesis_prompt(strategy: str = "balanced") -> str:
    """
    Generate the synthesis system prompt based on the selected strategy.

    Args:
        strategy: One of "conservative", "balanced", "aggressive"

    Returns:
        System prompt string tailored to the strategy
    """
    if strategy not in PROMPT_STRATEGIES:
        raise ValueError(
            f"Invalid strategy '{strategy}'. Must be one of: {list(PROMPT_STRATEGIES.keys())}"
        )

    config = PROMPT_STRATEGIES[strategy]

    # Base persona
    if strategy == "conservative":
        persona = "You are a friendly Australian local who loves sharing fun facts about suburbs."
    elif strategy == "balanced":
        persona = "You are a sharp Australian cultural commentator who writes hilarious, observational comedy about suburban life. Think: The Chaser meets Kath & Kim meets stand-up comedy at a pub roast."
    else:  # aggressive
        persona = "You are a fearless Australian satirist who exposes the absurd truths about suburban life. Think: John Clarke meets Chris Lilley with the bite of a angry pub comic."

    # Tone instructions
    tone_instruction = f"TONE: {config['synthesis_tone']}."

    # Avoid topics
    avoid_str = ", ".join(config["avoid_topics"])
    avoid_instruction = f"STRICTLY AVOID: {avoid_str}."

    # Encourage topics
    if config["encourage_topics"]:
        encourage_str = ", ".join(config["encourage_topics"])
        encourage_instruction = (
            f"FOCUS ON: {encourage_str}. Be SPECIFIC with brand names, car models, coffee orders, clothing brands, and daily routines."
        )
    else:
        encourage_instruction = ""

    # Edge-level specific guidance
    if strategy == "conservative":
        edge_guidance = "Keep it warm and fuzzy. Locals should smile and nod."
    elif strategy == "balanced":
        edge_guidance = "Punch UP at pretensions, not DOWN at genuine struggles. Mean enough to be funny, warm enough that locals would laugh along."
    else:  # aggressive
        edge_guidance = "Expose hypocrisy and absurdity mercilessly. If it makes the pretentious uncomfortable, you're doing it right. But NEVER punch down at marginalized groups."

    full_prompt = f"""{persona}

MANDATORY: You MUST produce valid JSON. No prose, no markdown fences, no preamble.

Output this exact JSON schema:
{{
    "stereotypes": [
        {{
            "archetype_name": "...",
            "description": "...",
            "typical_behaviors": ["...", "..."],
            "brands_things": ["...", "..."],
            "quotes": ["...", "..."],
            "citations": ["url1", "url2"],
            "snippets_used": ["snippet summary 1", "snippet summary 2"]
        }}
    ],
    "local_drama": [
        {{
            "title": "...",
            "description": "...",
            "why_funny": "...",
            "citations": ["url1"],
            "snippets_used": ["snippet summary"]
        }}
    ],
    "resident_personas": [
        {{
            "name": "...",
            "age_range": "...",
            "occupation_vibe": "...",
            "weekend_routine": "...",
            "uniform": "...",
            "vehicle": "...",
            "coffee_order": "...",
            "instagram_aesthetic": "...",
            "citations": ["url1"],
            "snippets_used": ["snippet summary"]
        }}
    ]
}}

{tone_instruction}
{avoid_instruction}
{encourage_instruction}

TECHNIQUES FOR VIRAL CONTENT:
- Create exaggerated personas that are instantly recognizable archetypes
- Include 1-2 highly specific details that make locals say "OMG that's SO [suburb]"
- Local drama should feel petty and ridiculous (bin collection disputes, parking wars, cafe reviews)
- Use contrast: "This person drives X but thinks they drive Y"
- {edge_guidance}

CITATION RULES:
- "citations" must reference real URLs from the search results
- "snippets_used" must list every search result that contributed information
- You can creatively interpret vague snippets into specific comedic details
- Fabricate specific details (brands, routines) that fit the archetype even if not explicitly in snippets

TARGET: Enough specific, memorable detail for a 400-word Instagram script that makes people tag their friends saying "this is literally us"."""

    return full_prompt


def get_strategy_info(strategy: str = "balanced") -> dict:
    """
    Get detailed info about a strategy.

    Returns:
        Dict with all strategy configuration
    """
    if strategy not in PROMPT_STRATEGIES:
        raise ValueError(
            f"Invalid strategy '{strategy}'. Must be one of: {list(PROMPT_STRATEGIES.keys())}"
        )

    return PROMPT_STRATEGIES[strategy].copy()


if __name__ == "__main__":
    # Demo usage
    import json

    print("Available Strategies:")
    print("=" * 60)
    for key, value in PROMPT_STRATEGIES.items():
        print(f"\n{key.upper()}: {value['name']}")
        print(f"Description: {value['description']}")
        print(f"Edge Level: {value['edge_level']}")
        print(f"Search Terms: {', '.join(value['search_terms'])}")
        print(f"Avoid: {', '.join(value['avoid_topics'])}")
        if value.get('encourage_topics'):
            print(f"Encourage: {', '.join(value['encourage_topics'])}")

    print("\n\n" + "=" * 60)
    print("Sample Queries (Balanced Strategy - Bondi, NSW):")
    print("=" * 60)
    queries = get_search_queries("Bondi", "NSW", "balanced")
    for q in queries:
        print(f"[{q['category']}] {q['query']}")

    print("\n\n" + "=" * 60)
    print("Sample Synthesis Prompt Preview (Balanced):")
    print("=" * 60)
    prompt = get_synthesis_prompt("balanced")
    print(prompt[:500] + "...")  # Preview first 500 chars