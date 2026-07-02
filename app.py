import os
from flask import Flask
from config import Config
from database import db
from routes.main import main_bp

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(Config)
    
    # Initialize Database
    db.init_app(app)
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    # Create tables
    with app.app_context():
        db.create_all()
        print("Database initialized successfully.")
        
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
