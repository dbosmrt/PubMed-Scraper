"""
Unit tests for paper type classifier.
"""

import pytest

from src.crawlers.base import Author, Paper
from src.processors.classifier import PaperClassifier
from src.shared.constants import PaperType, Source


@pytest.fixture
def classifier():
    return PaperClassifier(use_ml=False)


@pytest.fixture
def sample_paper():
    return Paper(
        id="12345",
        source=Source.PUBMED,
        title="",
        abstract="",
    )


class TestPaperClassifier:
    """Tests for PaperClassifier."""

    def test_classify_systematic_review(self, classifier, sample_paper):
        sample_paper.title = "A systematic review of cancer biomarkers"
        sample_paper.abstract = "We conducted a systematic review of the literature..."
        
        result = classifier.classify(sample_paper)
        assert result == PaperType.SYSTEMATIC_REVIEW

    def test_classify_meta_analysis(self, classifier, sample_paper):
        sample_paper.title = "Meta-analysis of treatment outcomes"
        sample_paper.abstract = "This meta-analysis pools data from multiple studies..."
        
        result = classifier.classify(sample_paper)
        assert result == PaperType.META_ANALYSIS

    def test_classify_clinical_trial(self, classifier, sample_paper):
        sample_paper.title = "A randomized controlled trial of drug X"
        sample_paper.abstract = "This RCT evaluates the efficacy of..."
        
        result = classifier.classify(sample_paper)
        assert result == PaperType.RANDOMIZED_CONTROLLED_TRIAL

    def test_classify_case_report(self, classifier, sample_paper):
        sample_paper.title = "A case of rare genetic mutation"
        sample_paper.abstract = "We present a case report of a patient..."
        
        result = classifier.classify(sample_paper)
        assert result == PaperType.CASE_REPORT

    def test_classify_review(self, classifier, sample_paper):
        sample_paper.title = "Literature review of treatment approaches"
        sample_paper.abstract = "This review summarizes current knowledge..."
        
        result = classifier.classify(sample_paper)
        assert result == PaperType.REVIEW

    def test_classify_observational(self, classifier, sample_paper):
        sample_paper.title = "A cohort study of patient outcomes"
        sample_paper.abstract = "We conducted a retrospective cohort study..."
        
        result = classifier.classify(sample_paper)
        assert result == PaperType.COHORT_STUDY

    def test_classify_research_article(self, classifier, sample_paper):
        sample_paper.title = "Novel biomarker discovery in cancer patients"
        sample_paper.abstract = (
            "We investigated the expression of genes in cancer cells. "
            "Methods: We analyzed samples from 200 patients. "
            "Results: Our findings show significant differences (p < 0.05). "
            "Conclusions: These results suggest a new therapeutic approach."
        )
        
        result = classifier.classify(sample_paper)
        assert result == PaperType.RESEARCH_ARTICLE

    def test_respects_existing_classification(self, classifier, sample_paper):
        sample_paper.paper_type = PaperType.CLINICAL_TRIAL
        sample_paper.title = "This looks like a review"
        
        result = classifier.classify(sample_paper)
        assert result == PaperType.CLINICAL_TRIAL

    def test_batch_classification(self, classifier):
        papers = [
            Paper(id="1", title="Systematic review", abstract="", source=Source.PUBMED),
            Paper(id="2", title="Meta-analysis", abstract="", source=Source.PUBMED),
            Paper(id="3", title="Case report", abstract="", source=Source.PUBMED),
        ]
        
        results = classifier.classify_batch(papers)
        
        assert len(results) == 3
        assert results[0][1] == PaperType.SYSTEMATIC_REVIEW
        assert results[1][1] == PaperType.META_ANALYSIS
        assert results[2][1] == PaperType.CASE_REPORT
