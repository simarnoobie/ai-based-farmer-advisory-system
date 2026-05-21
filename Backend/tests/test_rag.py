"""
Tests for the TF-IDF RAG retrieval in punjab_policy_knowledge.py.
No mocking needed — pure function, no I/O.
"""
import pytest
from punjab_policy_knowledge import retrieve_policy_context


def test_irrigation_query_returns_pmksy():
    results = retrieve_policy_context("drip irrigation water conservation")
    titles = [r["title"] for r in results]
    assert "PMKSY Per Drop More Crop" in titles


def test_insurance_query_returns_pmfby():
    results = retrieve_policy_context("crop insurance loss flood drought")
    titles = [r["title"] for r in results]
    assert "PMFBY Crop Insurance" in titles


def test_pension_query_returns_maandhan():
    results = retrieve_policy_context("farmer pension retirement social security")
    titles = [r["title"] for r in results]
    assert "PM Kisan Maandhan Yojana" in titles


def test_empty_query_returns_empty_list():
    assert retrieve_policy_context("") == []
    assert retrieve_policy_context("   ") == []


def test_top_k_respected():
    results = retrieve_policy_context("farming agriculture crop", top_k=2)
    assert len(results) <= 2


def test_result_has_required_keys():
    results = retrieve_policy_context("wheat paddy msp price support")
    assert len(results) > 0
    for doc in results:
        assert "title" in doc
        assert "content" in doc
        assert "source" in doc
