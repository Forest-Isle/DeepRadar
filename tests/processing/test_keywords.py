from deepradar.processing.keywords import is_ai_related


SAMPLE_CONFIG = {
    "categories": {
        "ai_relevance_keywords": {
            "high": ["ai", "machine learning", "llm"],
            "medium": ["transformer", "embedding"],
            "low": ["automation"],
        },
        "categories": [
            {"name": "LLM", "keywords": ["gpt", "claude"], "weight": 1.2},
            {"name": "CV", "keywords": ["computer vision", "diffusion"], "weight": 1.0},
        ],
    }
}


def test_matches_high_keyword():
    assert is_ai_related("New AI model released", "", SAMPLE_CONFIG) is True


def test_matches_category_keyword():
    assert is_ai_related("GPT-5 announced", "", SAMPLE_CONFIG) is True


def test_no_match():
    assert is_ai_related("Cooking recipes today", "best pasta ever", SAMPLE_CONFIG) is False


def test_matches_in_text_body():
    assert is_ai_related("Untitled", "uses machine learning for predictions", SAMPLE_CONFIG) is True


def test_case_insensitive():
    assert is_ai_related("NEW LLM BENCHMARK", "", SAMPLE_CONFIG) is True


def test_empty_config_returns_false():
    assert is_ai_related("anything", "", {"categories": {}}) is False
