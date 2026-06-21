"""Pi-coder web search — standalone Azure-backed search service.

Usage:
    from pi_coder_search.service import search
    result = search("Bondi suburb stereotype Reddit", max_results=5)
    # → {"query": ..., "total_results": 3, "results": [{"title": ..., "url": ..., "content": ...}, ...]}
"""
