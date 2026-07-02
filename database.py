from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class JobDescription(db.Model):
    __tablename__ = 'job_descriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, default="Senior AI Engineer")
    raw_text = db.Column(db.Text, nullable=False)
    skills = db.Column(db.Text, nullable=True) # JSON list of skills
    experience_required = db.Column(db.Float, nullable=True, default=5.0)
    seniority = db.Column(db.String(100), nullable=True, default="Senior")
    location = db.Column(db.String(255), nullable=True, default="Pune/Noida, India")
    parsed_data = db.Column(db.Text, nullable=True) # JSON string of extra parsed requirements
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_skills(self, skills_list):
        self.skills = json.dumps(skills_list)

    def get_skills(self):
        return json.loads(self.skills) if self.skills else []

    def set_parsed_data(self, data_dict):
        self.parsed_data = json.dumps(data_dict)

    def get_parsed_data(self):
        return json.loads(self.parsed_data) if self.parsed_data else {}


class Candidate(db.Model):
    __tablename__ = 'candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.String(50), unique=True, nullable=True) # E.g. CAND_0000001
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(100), nullable=True)
    linkedin = db.Column(db.String(255), nullable=True)
    github = db.Column(db.String(255), nullable=True)
    location = db.Column(db.String(255), nullable=True)
    raw_text = db.Column(db.Text, nullable=True) # Raw extracted text from PDF
    
    # Parsed structured profile stored as JSON strings
    skills = db.Column(db.Text, nullable=True) # JSON list of dicts: name, proficiency, endorsements, duration
    career_history = db.Column(db.Text, nullable=True) # JSON list of dicts: company, title, start_date, end_date, etc.
    education = db.Column(db.Text, nullable=True) # JSON list of dicts: institution, degree, field_of_study, tier, etc.
    certifications = db.Column(db.Text, nullable=True) # JSON list of dicts: name, issuer, year
    languages = db.Column(db.Text, nullable=True) # JSON list of dicts: language, proficiency
    redrob_signals = db.Column(db.Text, nullable=True) # JSON dict of Redrob platform telemetry
    
    # AI cache
    embedding = db.Column(db.LargeBinary, nullable=True) # Cached vector embedding
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Setters and Getters for JSON fields
    def set_skills(self, skills_list):
        self.skills = json.dumps(skills_list)
    def get_skills(self):
        return json.loads(self.skills) if self.skills else []

    def set_career_history(self, career_list):
        self.career_history = json.dumps(career_list)
    def get_career_history(self):
        return json.loads(self.career_history) if self.career_history else []

    def set_education(self, edu_list):
        self.education = json.dumps(edu_list)
    def get_education(self):
        return json.loads(self.education) if self.education else []

    def set_certifications(self, certs_list):
        self.certifications = json.dumps(certs_list)
    def get_certifications(self):
        return json.loads(self.certifications) if self.certifications else []

    def set_languages(self, langs_list):
        self.languages = json.dumps(langs_list)
    def get_languages(self):
        return json.loads(self.languages) if self.languages else []

    def set_redrob_signals(self, signals_dict):
        self.redrob_signals = json.dumps(signals_dict)
    def get_redrob_signals(self):
        return json.loads(self.redrob_signals) if self.redrob_signals else {}


class Evaluation(db.Model):
    __tablename__ = 'evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_descriptions.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidates.id'), nullable=False)
    
    # Subscores (0 - 100)
    score_semantic = db.Column(db.Float, nullable=False)
    score_skills = db.Column(db.Float, nullable=False)
    score_experience = db.Column(db.Float, nullable=False)
    score_projects = db.Column(db.Float, nullable=False)
    score_education = db.Column(db.Float, nullable=False)
    score_certifications = db.Column(db.Float, nullable=False)
    score_career_growth = db.Column(db.Float, nullable=False)
    score_behavior = db.Column(db.Float, nullable=False)
    score_activity = db.Column(db.Float, nullable=False)
    
    # Aggregated results
    score_final = db.Column(db.Float, nullable=False)
    rank = db.Column(db.Integer, nullable=True) # Final calculated rank for this job
    recommendation = db.Column(db.String(50), nullable=False) # Strong Hire, Hire, Consider, Reject
    
    # AI Explanation
    explanation = db.Column(db.Text, nullable=True) # JSON dict: {strengths: [], gaps: [], text: ""}
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    job = db.relationship('JobDescription', backref=db.backref('evaluations', lazy=True, cascade="all, delete-orphan"))
    candidate = db.relationship('Candidate', backref=db.backref('evaluations', lazy=True, cascade="all, delete-orphan"))

    def set_explanation(self, expl_dict):
        self.explanation = json.dumps(expl_dict)
    def get_explanation(self):
        return json.loads(self.explanation) if self.explanation else {"strengths": [], "gaps": [], "text": ""}
