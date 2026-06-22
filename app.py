"""
app.py

Flask web app for the ATS Resume Checker.

Routes:
    GET  /            - the upload/paste form
    POST /score       - scores submitted text, renders results
    POST /api/score    - same scoring logic, returns JSON (for API use)
"""

from flask import Flask, render_template, request, jsonify

from ats_scorer import ATSScorer

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", report=None)


@app.route("/score", methods=["POST"])
def score():
    resume_text = request.form.get("resume_text", "")
    job_description = request.form.get("job_description", "")

    error = None
    report = None
    if not resume_text.strip():
        error = "Paste your resume text before running the check."
    else:
        scorer = ATSScorer(resume_text, job_description=job_description)
        report = scorer.score()

    return render_template(
        "index.html",
        report=report,
        error=error,
        resume_text=resume_text,
        job_description=job_description,
    )


@app.route("/api/score", methods=["POST"])
def api_score():
    """JSON API endpoint -- lets this be used as a backend for other tools."""
    data = request.get_json(silent=True) or {}
    resume_text = data.get("resume_text", "")
    job_description = data.get("job_description", "")

    if not resume_text.strip():
        return jsonify({"error": "resume_text is required"}), 400

    scorer = ATSScorer(resume_text, job_description=job_description)
    report = scorer.score()
    return jsonify(report.to_dict())


if __name__ == "__main__":
    app.run(debug=True)
