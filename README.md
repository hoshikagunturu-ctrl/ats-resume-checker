# ATS Resume Checker

A Flask web app that scores a resume against a job description the same way an
Applicant Tracking System (ATS) does — checking formatting, section structure,
keyword overlap, and content quality — and returns a 0-100 score with a
detailed breakdown.

I built this after manually reviewing resumes and reverse-engineering the
checks ATS tools actually run. Instead of guessing whether a resume will get
filtered out, this gives a concrete, explainable score.

## Why this exists

Most ATS scoring tools are black boxes — you get a number with no explanation.
This project makes every check transparent: you can see exactly which rule
passed or failed and why, in plain language.

## Features

- **Formatting checks** — flags table/column artifacts that break ATS parsers, checks resume length
- **Structure checks** — verifies standard sections (Education, Experience, Projects, Skills, Contact) are present
- **Keyword matching** — tokenizes resume and job description text, reports matched/missing keywords
- **Content quality checks** — flags weak filler phrases ("helped with", "responsible for"), rewards quantified bullet points, verifies contact info is present
- **JSON API** (`/api/score`) so the scoring engine can be used standalone, outside the web UI
- 15 unit tests covering the scoring logic

## Tech stack

Python 3, Flask, Jinja2. No external ML/NLP libraries — the tokenizer and
scoring logic are written from scratch in `ats_scorer.py`.

## Project structure

```
ats-resume-checker/
├── app.py                  # Flask routes (UI + JSON API)
├── ats_scorer.py           # Core scoring engine (no Flask dependency)
├── templates/
│   └── index.html          # Single-page UI
├── tests/
│   └── test_ats_scorer.py  # Unit tests
├── sample_resume.txt        # Try it with this
├── requirements.txt
└── LICENSE
```

## Running it locally

```bash
git clone https://github.com/<your-username>/ats-resume-checker.git
cd ats-resume-checker
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000` and paste in a resume (try `sample_resume.txt`)
plus an optional job description.

## Running the tests

```bash
python -m unittest discover tests -v
```

## How scoring works

The total score is out of 100, split across four weighted categories:

| Category          | Weight | What it checks                                      |
|--------------------|:------:|-------------------------------------------------------|
| Formatting          | 20     | No table/column artifacts, reasonable 1-page length    |
| Structure            | 25     | Standard sections present (Education, Skills, etc.)   |
| Keyword match        | 30     | Overlap between resume and job description keywords    |
| Content quality      | 25     | Contact info, quantified bullets, no filler phrases    |

The weights are defined as constants in `ats_scorer.py` and easy to adjust.

## Possible improvements

- PDF/DOCX upload instead of paste-only
- Synonym-aware keyword matching (e.g. "ML" vs "machine learning")
- Per-section feedback inline rather than one flat checklist

## License

MIT — see [LICENSE](LICENSE).
