"""
ats_scorer.py

Core scoring engine for the ATS Resume Checker.

Given a resume's raw text and (optionally) a target job description,
this module produces a 0-100 score plus a breakdown of checks across
four categories:

    1. Formatting     - things that break or confuse ATS parsers
    2. Structure       - presence of standard resume sections
    3. Keyword match   - overlap between resume and job description
    4. Content quality - quantified bullets, length, contact info

The scoring weights are intentionally simple and documented inline so
they're easy to defend in an interview ("why does keyword match count
for 30 points?") rather than a black box.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Standard resume section headers we look for. Each entry is a list of
# acceptable spellings/synonyms for that section.
SECTION_SYNONYMS: dict[str, list[str]] = {
    "contact": ["email", "phone", "linkedin", "github"],
    "education": ["education", "academic background"],
    "experience": ["experience", "work experience", "internship", "internships"],
    "projects": ["projects", "personal projects", "academic projects"],
    "skills": ["skills", "technical skills", "tools", "technologies"],
}

# Words that, when found in bullet points, indicate the bullet is
# quantified (i.e. backed by a number or measurable outcome).
QUANTIFIER_PATTERN = re.compile(r"\d+(\.\d+)?\s*(%|x|ms|s|k|million|users|percent)?")

# A lightweight English stopword list (kept small on purpose -- this is a
# resume tool, not a full NLP library, so we avoid heavy dependencies).
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "with", "for", "to", "of", "in",
    "on", "at", "by", "is", "are", "was", "were", "be", "been", "as",
    "this", "that", "it", "its", "from", "into", "such", "will", "we",
    "you", "your", "our", "their", "i", "they", "he", "she",
}


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, and split into words minus stopwords."""
    words = re.findall(r"[a-zA-Z][a-zA-Z+#.]*", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def _keyword_set(text: str) -> set[str]:
    return set(_tokenize(text))


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """A single pass/fail (or partial) check with a human-readable note."""
    label: str
    passed: bool
    points: float
    max_points: float
    note: str = ""


@dataclass
class ScoreReport:
    """Full output of scoring a resume."""
    total_score: float
    max_score: float
    checks: list[CheckResult] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    missing_keywords: list[str] = field(default_factory=list)

    @property
    def percentage(self) -> int:
        if self.max_score == 0:
            return 0
        return round((self.total_score / self.max_score) * 100)

    def to_dict(self) -> dict:
        return {
            "score": self.percentage,
            "total_score": round(self.total_score, 1),
            "max_score": self.max_score,
            "checks": [vars(c) for c in self.checks],
            "matched_keywords": self.matched_keywords,
            "missing_keywords": self.missing_keywords,
        }


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class ATSScorer:
    """
    Scores resume text against ATS-friendliness criteria and, optionally,
    a target job description.

    Usage:
        scorer = ATSScorer(resume_text, job_description=jd_text)
        report = scorer.score()
        print(report.percentage)
    """

    # Category weights out of 100. Kept as class constants so they're
    # easy to tune and explain.
    WEIGHT_FORMATTING = 20
    WEIGHT_STRUCTURE = 25
    WEIGHT_KEYWORDS = 30
    WEIGHT_CONTENT = 25

    def __init__(self, resume_text: str, job_description: Optional[str] = None):
        if not resume_text or not resume_text.strip():
            raise ValueError("resume_text must not be empty")
        self.resume_text = resume_text
        self.job_description = job_description

    # -- public API ---------------------------------------------------

    def score(self) -> ScoreReport:
        checks: list[CheckResult] = []

        checks.extend(self._check_formatting())
        checks.extend(self._check_structure())
        keyword_checks, matched, missing = self._check_keywords()
        checks.extend(keyword_checks)
        checks.extend(self._check_content_quality())

        total = sum(c.points for c in checks)
        max_total = sum(c.max_points for c in checks)

        return ScoreReport(
            total_score=total,
            max_score=max_total,
            checks=checks,
            matched_keywords=matched,
            missing_keywords=missing,
        )

    # -- formatting -----------------------------------------------------

    def _check_formatting(self) -> list[CheckResult]:
        text = self.resume_text
        results = []

        # Tables/columns often show up as repeated long runs of spaces
        # or tabs when copy-pasted out of a PDF -- a common ATS trap.
        suspicious_gaps = len(re.findall(r"[ ]{6,}|\t{2,}", text))
        passed = suspicious_gaps == 0
        results.append(CheckResult(
            label="No multi-column / table layout artifacts",
            passed=passed,
            points=self.WEIGHT_FORMATTING * 0.5 if passed else 0,
            max_points=self.WEIGHT_FORMATTING * 0.5,
            note="Clean single-column text." if passed
            else f"Found {suspicious_gaps} spots that look like table/column "
                 "artifacts -- these often confuse ATS parsers.",
        ))

        # Length: 1-page resumes for internships are roughly 300-700 words.
        word_count = len(text.split())
        length_ok = 250 <= word_count <= 800
        results.append(CheckResult(
            label="Resume length within 1-page range",
            passed=length_ok,
            points=self.WEIGHT_FORMATTING * 0.5 if length_ok else self.WEIGHT_FORMATTING * 0.25,
            max_points=self.WEIGHT_FORMATTING * 0.5,
            note=f"{word_count} words." + (
                "" if length_ok else " Aim for roughly 300-700 words on one page."
            ),
        ))

        return results

    # -- structure --------------------------------------------------------

    def _check_structure(self) -> list[CheckResult]:
        text_lower = self.resume_text.lower()
        results = []
        per_section = self.WEIGHT_STRUCTURE / len(SECTION_SYNONYMS)

        for section, synonyms in SECTION_SYNONYMS.items():
            found = any(s in text_lower for s in synonyms)
            results.append(CheckResult(
                label=f"Has '{section}' section",
                passed=found,
                points=per_section if found else 0,
                max_points=per_section,
                note="Found." if found else f"No {section} section detected.",
            ))
        return results

    # -- keyword matching ---------------------------------------------

    def _check_keywords(self) -> tuple[list[CheckResult], list[str], list[str]]:
        if not self.job_description or not self.job_description.strip():
            # No JD provided -- award full marks but flag it clearly,
            # since this category genuinely can't be evaluated without one.
            note = "No job description provided -- paste one for a real keyword match score."
            return (
                [CheckResult(
                    label="Keyword match vs job description",
                    passed=True,
                    points=self.WEIGHT_KEYWORDS,
                    max_points=self.WEIGHT_KEYWORDS,
                    note=note,
                )],
                [],
                [],
            )

        resume_kw = _keyword_set(self.resume_text)
        jd_kw = _keyword_set(self.job_description)

        if not jd_kw:
            return [], [], []

        matched = sorted(jd_kw & resume_kw)
        missing = sorted(jd_kw - resume_kw)
        match_ratio = len(matched) / len(jd_kw)
        points = round(match_ratio * self.WEIGHT_KEYWORDS, 1)

        check = CheckResult(
            label="Keyword match vs job description",
            passed=match_ratio >= 0.4,
            points=points,
            max_points=self.WEIGHT_KEYWORDS,
            note=f"{len(matched)}/{len(jd_kw)} job-description keywords found "
                 f"in resume ({round(match_ratio * 100)}%).",
        )
        return [check], matched, missing

    # -- content quality --------------------------------------------------

    def _check_content_quality(self) -> list[CheckResult]:
        text = self.resume_text
        results = []

        # Contact info: email + phone-like pattern
        has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
        has_phone = bool(re.search(r"(\+?\d[\d\s-]{8,}\d)", text))
        contact_ok = has_email and has_phone
        results.append(CheckResult(
            label="Email and phone number present",
            passed=contact_ok,
            points=self.WEIGHT_CONTENT * 0.2 if contact_ok else 0,
            max_points=self.WEIGHT_CONTENT * 0.2,
            note="Found both." if contact_ok
            else "Missing email and/or phone number.",
        ))

        # Quantified bullets: lines starting with a bullet-ish character
        # that also contain a number.
        bullet_lines = re.findall(r"^[\s]*[•\-*][^\n]+", text, flags=re.MULTILINE)
        quantified = [b for b in bullet_lines if QUANTIFIER_PATTERN.search(b)]
        ratio = (len(quantified) / len(bullet_lines)) if bullet_lines else 0
        results.append(CheckResult(
            label="Bullets include measurable outcomes (numbers/%)",
            passed=ratio >= 0.3,
            points=round(self.WEIGHT_CONTENT * 0.5 * min(ratio / 0.3, 1), 1),
            max_points=self.WEIGHT_CONTENT * 0.5,
            note=f"{len(quantified)}/{len(bullet_lines)} bullets are quantified."
            if bullet_lines else "No bullet points detected.",
        ))

        # Weak/filler verbs that recruiters and ATS keyword scans both
        # tend to penalize relative to strong action verbs.
        weak_verbs = ["helped", "worked on", "responsible for", "involved in"]
        weak_hits = sum(text.lower().count(v) for v in weak_verbs)
        weak_ok = weak_hits == 0
        results.append(CheckResult(
            label="Avoids weak filler phrases",
            passed=weak_ok,
            points=self.WEIGHT_CONTENT * 0.3 if weak_ok else self.WEIGHT_CONTENT * 0.15,
            max_points=self.WEIGHT_CONTENT * 0.3,
            note="No filler phrases found." if weak_ok
            else f"Found {weak_hits} filler phrase(s) like 'helped with' or "
                 "'responsible for' -- replace with a strong action verb.",
        ))

        return results
