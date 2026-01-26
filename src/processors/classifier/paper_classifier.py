"""
PubMed Scraper - Paper Type Classifier

ML-based and rule-based classification of papers into types:
Research Article, Review, Meta-Analysis, Clinical Trial, etc.
"""

import re
from typing import Any

from src.crawlers.base import Paper
from src.shared.constants import PaperType
from src.shared.logging import LoggerMixin


class PaperClassifier(LoggerMixin):
    """
    Hybrid classifier using rules and ML for paper type classification.

    Priority:
    1. Existing paper_type if already set (from source metadata)
    2. Rule-based classification (fast, high precision)
    3. ML-based classification (fallback for ambiguous cases)
    """

    # Keywords for rule-based classification
    REVIEW_KEYWORDS = [
        "systematic review",
        "literature review",
        "narrative review",
        "scoping review",
        "umbrella review",
        "state of the art",
        "comprehensive review",
        "critical review",
    ]

    META_ANALYSIS_KEYWORDS = [
        "meta-analysis",
        "meta analysis",
        "pooled analysis",
        "quantitative synthesis",
    ]

    CLINICAL_TRIAL_KEYWORDS = [
        "randomized controlled trial",
        "randomised controlled trial",
        "rct",
        "clinical trial",
        "phase i",
        "phase ii",
        "phase iii",
        "phase iv",
        "double-blind",
        "placebo-controlled",
    ]

    CASE_REPORT_KEYWORDS = [
        "case report",
        "case presentation",
        "case study",
        "a case of",
    ]

    CASE_SERIES_KEYWORDS = [
        "case series",
        "consecutive patients",
        "consecutive cases",
    ]

    OBSERVATIONAL_KEYWORDS = [
        "cohort study",
        "cross-sectional",
        "case-control",
        "retrospective study",
        "prospective study",
        "observational study",
        "population-based study",
    ]

    EDITORIAL_KEYWORDS = [
        "editorial",
        "editor's note",
        "from the editor",
    ]

    LETTER_KEYWORDS = [
        "letter to the editor",
        "correspondence",
        "letter:",
        "reply to",
        "response to",
    ]

    COMMENTARY_KEYWORDS = [
        "commentary",
        "perspective",
        "opinion",
        "viewpoint",
    ]

    def __init__(self, use_ml: bool = True) -> None:
        """
        Initialize classifier.

        Args:
            use_ml: Whether to use ML model for ambiguous cases
        """
        self.use_ml = use_ml
        self._ml_model = None

    def classify(self, paper: Paper) -> PaperType:
        """
        Classify a paper into a type.

        Args:
            paper: Paper object with title and abstract

        Returns:
            Classified paper type
        """
        # If already classified by source, trust it
        if paper.paper_type != PaperType.UNKNOWN:
            return paper.paper_type

        # Combine title and abstract for analysis
        text = f"{paper.title} {paper.abstract}".lower()

        # Rule-based classification (in order of specificity)
        paper_type = self._rule_based_classify(text)
        if paper_type != PaperType.UNKNOWN:
            self.logger.debug(
                "Classified by rules",
                paper_id=paper.id,
                paper_type=str(paper_type),
            )
            return paper_type

        # ML-based fallback
        if self.use_ml and self._ml_model is not None:
            paper_type = self._ml_classify(text)
            if paper_type != PaperType.UNKNOWN:
                self.logger.debug(
                    "Classified by ML",
                    paper_id=paper.id,
                    paper_type=str(paper_type),
                )
                return paper_type

        # Default to research article if it looks like original research
        if self._looks_like_research(text):
            return PaperType.RESEARCH_ARTICLE

        return PaperType.UNKNOWN

    def _rule_based_classify(self, text: str) -> PaperType:
        """Apply rule-based classification."""
        # Check in order of specificity (most specific first)

        # Meta-analysis (subset of reviews, check first)
        if any(kw in text for kw in self.META_ANALYSIS_KEYWORDS):
            return PaperType.META_ANALYSIS

        # Systematic review
        if "systematic review" in text:
            return PaperType.SYSTEMATIC_REVIEW

        # General review
        if any(kw in text for kw in self.REVIEW_KEYWORDS):
            return PaperType.REVIEW

        # Randomized controlled trial (subset of clinical trials)
        if any(kw in text for kw in ["randomized controlled trial", "randomised controlled trial", "rct"]):
            return PaperType.RANDOMIZED_CONTROLLED_TRIAL

        # Clinical trial
        if any(kw in text for kw in self.CLINICAL_TRIAL_KEYWORDS):
            return PaperType.CLINICAL_TRIAL

        # Case series (check before case report)
        if any(kw in text for kw in self.CASE_SERIES_KEYWORDS):
            return PaperType.CASE_SERIES

        # Case report
        if any(kw in text for kw in self.CASE_REPORT_KEYWORDS):
            return PaperType.CASE_REPORT

        # Observational studies
        if any(kw in text for kw in self.OBSERVATIONAL_KEYWORDS):
            return PaperType.OBSERVATIONAL_STUDY

        # Cohort specifically
        if "cohort" in text and ("study" in text or "analysis" in text):
            return PaperType.COHORT_STUDY

        # Editorial
        if any(kw in text for kw in self.EDITORIAL_KEYWORDS):
            return PaperType.EDITORIAL

        # Letter
        if any(kw in text for kw in self.LETTER_KEYWORDS):
            return PaperType.LETTER

        # Commentary
        if any(kw in text for kw in self.COMMENTARY_KEYWORDS):
            return PaperType.COMMENTARY

        return PaperType.UNKNOWN

    def _looks_like_research(self, text: str) -> bool:
        """Check if text looks like original research."""
        research_indicators = [
            "we investigated",
            "we examined",
            "we analyzed",
            "we analysed",
            "we studied",
            "we found",
            "our results",
            "our findings",
            "our study",
            "this study",
            "methods:",
            "results:",
            "conclusions:",
            "objective:",
            "background:",
            "n =",
            "p <",
            "p =",
            "95% ci",
            "confidence interval",
            "statistical",
            "significant",
        ]

        matches = sum(1 for indicator in research_indicators if indicator in text)
        return matches >= 3

    def _ml_classify(self, text: str) -> PaperType:
        """ML-based classification (placeholder for actual model)."""
        # TODO: Implement actual ML classification
        # Could use:
        # - Fine-tuned BERT/SciBERT
        # - Trained sklearn classifier on labeled data
        # - Zero-shot classification with sentence-transformers
        return PaperType.UNKNOWN

    def classify_batch(self, papers: list[Paper]) -> list[tuple[Paper, PaperType]]:
        """
        Classify multiple papers.

        Args:
            papers: List of papers to classify

        Returns:
            List of (paper, paper_type) tuples
        """
        results = []
        for paper in papers:
            paper_type = self.classify(paper)
            results.append((paper, paper_type))
        return results

    def get_classification_stats(self, papers: list[Paper]) -> dict[str, int]:
        """
        Get statistics on paper type distribution.

        Args:
            papers: List of papers

        Returns:
            Dictionary mapping paper_type to count
        """
        stats: dict[str, int] = {}
        for paper in papers:
            paper_type = str(self.classify(paper))
            stats[paper_type] = stats.get(paper_type, 0) + 1
        return stats
