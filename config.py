import os

class Config:
    # Base directories
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'exports')
    MODEL_CACHE_FOLDER = os.path.join(BASE_DIR, 'models')
    
    # Ensure folders exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(EXPORT_FOLDER, exist_ok=True)
    os.makedirs(MODEL_CACHE_FOLDER, exist_ok=True)
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'airecruiter_secret_key_for_session_token'
    
    # Embedding Settings
    EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
    
    # Target Locations for Job Description (Senior AI Engineer - Founding Team)
    TARGET_LOCATIONS = ['pune', 'noida', 'delhi ncr', 'hyderabad', 'mumbai', 'bangalore']
    
    # Default Ranking Weights
    DEFAULT_WEIGHTS = {
        'semantic': 0.30,
        'skills': 0.25,
        'experience': 0.15,
        'projects': 0.10,
        'education': 0.05,
        'certifications': 0.05,
        'career_growth': 0.05,
        'behavior': 0.03,
        'activity': 0.02
    }
    
    # Recommendation thresholds
    THRESHOLD_STRONG_HIRE = 85.0
    THRESHOLD_HIRE = 70.0
    THRESHOLD_CONSIDER = 50.0
