# AIRecruiter: Intelligent Candidate Discovery & Ranking Platform

AIRecruiter is a production-quality, high-performance candidate sourcing and semantic ranking system designed as an AI Recruiter MVP. 

In addition to serving as a beautiful recruitment telemetry interface for HR specialists, the platform integrates a lightning-fast two-stage retrieval and ranking engine (`rank.py`) designed specifically to solve the **Intelligent Candidate Discovery & Ranking Challenge** within the 5-minute CPU constraint.

---

## 🌟 Key Features

1. **Two-Stage Retrieve & Rank Pipeline**: Screens a pool of 100,000 candidates using fast-filtering keywords and eligibility parameters before running deep transformer embeddings, ensuring the entire process completes in under 3 minutes on standard CPUs.
2. **Robust Honeypot Detection**: Prevents disqualification by scanning candidate profiles for subtly impossible data (e.g., expert in 10 skills with 0 months experience, or claimed tenure exceeding job date intervals) and filtering them out of the top 100 list.
3. **Multi-Signal Quality Scoring**: Normalizes and aggregates nine independent criteria:
   - *Semantic Match (30%)*: Cosine similarity between resume and job description.
   - *Skills Fit (25%)*: Synonyms-resolved Jaccard similarity weighted by proficiency.
   - *Experience Match (15%)*: Years of experience calibration and seniority check.
   - *Projects Relevance (10%)*: Project text match to job duties.
   - *Education (5%)*: Institution tiering and degree levels.
   - *Certifications (5%)*: Weighting of cloud/ML qualifications.
   - *Career Growth (5%)*: Trajectory progression tracking and job-hopping penalties.
   - *Platform Behavior (3%)*: Candidate responsiveness and interview completion history.
   - *Activity Metrics (2%)*: Code contributions and platform views.
4. **Explainable AI Engine**: Rather than simple numerical outputs, the ranker compiles granular strengths, gaps, and a structured 1-2 sentence justification for every candidate.
5. **Interactive Telemetry Dashboard**: Visualizes candidate distributions, skill frequency clouds, experience curves, and radar charts.
6. **Polished Excel Exporter**: Outputs styled spreadsheet shortlists using custom row heights, auto-adjusted column widths, and color-coded recommendation cells.

---

## ⚙️ System Architecture

```
AIRecruiter/
│   app.py                  # Web application entry point (Flask)
│   config.py               # Settings, directories, and ranking weights
│   database.py             # SQLite models using Flask-SQLAlchemy
│   requirements.txt        # PIP packages list
│   rank.py                 # Challenge CLI ranking reproduction entry point
│   README.md               # User guide & documentation
│
├───routes/
│       main.py             # View controller blueprint (loads, runs, routes)
│
├───utils/
│       parser.py           # Text extractors & NLP parser
│       embedder.py         # SentenceTransformers & FAISS Search Index
│       ranker.py           # Scoring formulas, traps & consulting filters
│       exporter.py         # Styled openpyxl spreadsheet compiler
│       dashboard.py        # Analytics data compressor for Chart.js
│
├───templates/              # Jinja2 Layout Templates
│       base.html           # Sidebar skeleton frame
│       home.html           # Landing page
│       upload_jd.html      # JD paste/preview page
│       upload_resumes.html # Candidate pool manager
│       processing.html     # AJAX progress stepper
│       results.html        # Sortable shortlist table
│       details.html        # Comprehensive candidate report
│       dashboard.html      # Visual telemetry graphs
│
└───static/                 # Client assets
    ├───css/
    │       style.css       # Custom glassmorphic dark-theme styles
    └───js/
            main.js         # Upload drag-and-drop, AJAX & sorting triggers
```

---

## 🚀 Installation & Local Setup

### 1. Clone the repository and navigate to the project
```bash
git clone https://github.com/your-username/AIRecruiter.git
cd AIRecruiter
```

### 2. Set up virtual environment and install packages
Make sure you have Python 3.9+ installed on a CPU-only environment.
```bash
python -m venv venv
venv\Scripts\activate      # On Windows
source venv/bin/activate    # On macOS/Linux

pip install -r requirements.txt
```

### 3. Start the Web App Server
```bash
python app.py
```
Open your browser and navigate to `http://127.0.0.1:5000/`.

---

## 🏆 Challenge Submission & Reproduction

For Stage 3 code reproduction validation, you can trigger the evaluation pipeline from the terminal using the following command. The script automatically reads the job description from the bundle, screens the candidate pool, detects honeypots, calculates the multi-signal score, and outputs the formatted CSV.

### Commands to Run:
```bash
python rank.py --candidates ./dataandai/India_runs_data_and_ai_challenge/candidates.jsonl --out ./submission.csv
```

### Format Verification:
You can validate the output CSV formatting using the validator included in the bundle:
```bash
python ./dataandai/India_runs_data_and_ai_challenge/validate_submission.py ./submission.csv
```

---

## 🔬 Scoring Formulas & Weight Allocations

Weights are fully customizable in `config.py` under the `DEFAULT_WEIGHTS` dictionary. The default allocations are:

| Quality Signal | Default Weight | Metric Scope |
| :--- | :---: | :--- |
| **Semantic Match** | 30% | Cosine similarity between resume and job description text via `all-MiniLM-L6-v2`. |
| **Skills Match** | 25% | Skill intersection, resolving synonyms and weighting by proficiency. |
| **Experience** | 15% | Years of experience validation and Seniority Title checking. |
| **Projects** | 10% | Match of career description and project context to job responsibilities. |
| **Education** | 5% | Academic tiering (Tier-1 to Tier-4) and degree weight (PhD, MS, BE). |
| **Certifications** | 5% | Relevant qualifications in AI, Cloud (AWS/GCP/Azure) and DevOps. |
| **Career Growth** | 5% | Career progression tracking and job-hopping stability penalties. |
| **Behavior** | 3% | Platform responsiveness, response rate and OTW flags. |
| **Activity** | 2% | Code contributions (GitHub) and profile completeness rates. |

*Consulting-only careers and purely research backgrounds receive a 50% score penalty multiplier.*
