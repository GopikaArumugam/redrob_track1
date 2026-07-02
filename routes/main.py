import os
import json
import gzip
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app
from werkzeug.utils import secure_filename
from database import db, JobDescription, Candidate, Evaluation
from config import Config
from utils.parser import parse_resume_pdf, parse_job_description_text
from utils.ranker import rank_candidates, is_honeypot
from utils.exporter import generate_excel_report
from utils.dashboard import get_dashboard_stats
from utils.embedder import Embedder

main_bp = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main_bp.route('/')
def index():
    # Fetch job description counts
    jd_count = JobDescription.query.count()
    candidate_count = Candidate.query.count()
    eval_count = Evaluation.query.count()
    return render_template('home.html', jd_count=jd_count, candidate_count=candidate_count, eval_count=eval_count)

@main_bp.route('/upload_jd', methods=['GET', 'POST'])
def upload_jd():
    if request.method == 'POST':
        jd_text = request.form.get('jd_text', '').strip()
        jd_file = request.files.get('jd_file')
        
        # Check if text is pasted or file is uploaded
        if jd_file and allowed_file(jd_file.filename):
            filename = secure_filename(jd_file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            jd_file.save(file_path)
            
            # Use pdf parser (we reuse the resume text extractor)
            from utils.parser import extract_pdf_text
            extracted_text = extract_pdf_text(file_path)
            # Remove file
            try:
                os.remove(file_path)
            except:
                pass
            
            if not extracted_text:
                flash("Could not extract text from the PDF file. Please try pasting the text.", "danger")
                return redirect(url_for('main.upload_jd'))
            jd_text = extracted_text
            
        if not jd_text:
            flash("Please paste a job description or upload a valid PDF.", "danger")
            return redirect(url_for('main.upload_jd'))
            
        # Parse job description using our parser
        parsed_jd = parse_job_description_text(jd_text)
        
        # Delete old JDs to keep PoC clean
        JobDescription.query.delete()
        Evaluation.query.delete()
        
        # Save to DB
        job = JobDescription(
            title=parsed_jd["title"],
            raw_text=parsed_jd["raw_text"],
            experience_required=parsed_jd["experience_required"],
            seniority=parsed_jd["seniority"],
            location=parsed_jd["location"]
        )
        job.set_skills(parsed_jd["skills"])
        job.set_parsed_data(parsed_jd["parsed_data"])
        
        db.session.add(job)
        db.session.commit()
        
        flash("Job Description uploaded and parsed successfully!", "success")
        return redirect(url_for('main.upload_resumes'))
        
    # GET request
    job = JobDescription.query.first()
    return render_template('upload_jd.html', job=job)

@main_bp.route('/reset_jd')
def reset_jd():
    JobDescription.query.delete()
    Candidate.query.delete()
    Evaluation.query.delete()
    db.session.commit()
    flash("Database reset successfully! You can now load a new Job Description.", "info")
    return redirect(url_for('main.upload_jd'))

@main_bp.route('/upload_resumes', methods=['GET', 'POST'])
def upload_resumes():
    job = JobDescription.query.first()
    if not job:
        flash("Please upload a Job Description first.", "warning")
        return redirect(url_for('main.upload_jd'))
        
    if request.method == 'POST':
        # Check if individual files are uploaded
        uploaded_files = request.files.getlist('resume_files')
        
        saved_count = 0
        for f in uploaded_files:
            if f and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                f.save(file_path)
                
                # Parse resume PDF
                try:
                    parsed_cand = parse_resume_pdf(file_path)
                    
                    # Check duplicate
                    existing = Candidate.query.filter_by(name=parsed_cand["name"]).first()
                    if existing:
                        db.session.delete(existing) # overwrite
                        
                    # Save Candidate to DB
                    cand = Candidate(
                        candidate_id=parsed_cand["candidate_id"],
                        name=parsed_cand["name"],
                        email=parsed_cand["email"],
                        phone=parsed_cand["phone"],
                        linkedin=parsed_cand["linkedin"],
                        github=parsed_cand["github"],
                        location=parsed_cand["location"],
                        raw_text=parsed_cand["raw_text"]
                    )
                    cand.set_skills(parsed_cand["skills"])
                    cand.set_career_history(parsed_cand["career_history"])
                    cand.set_education(parsed_cand["education"])
                    cand.set_certifications(parsed_cand["certifications"])
                    cand.set_languages(parsed_cand["languages"])
                    cand.set_redrob_signals(parsed_cand["redrob_signals"])
                    
                    db.session.add(cand)
                    saved_count += 1
                except Exception as e:
                    print(f"Error parsing resume {filename}: {e}")
                finally:
                    # Clean up
                    try:
                        os.remove(file_path)
                    except:
                        pass
                        
        if saved_count > 0:
            db.session.commit()
            flash(f"Successfully uploaded and parsed {saved_count} resumes!", "success")
            return redirect(url_for('main.upload_resumes'))
            
    # List existing candidates
    candidates = Candidate.query.all()
    return render_template('upload_resumes.html', candidates=candidates, job=job)

@main_bp.route('/load_sample_pool')
def load_sample_pool():
    """Loads sample candidates from sample_candidates.json for validation."""
    job = JobDescription.query.first()
    if not job:
        flash("Please upload a Job Description first.", "warning")
        return redirect(url_for('main.upload_jd'))
        
    sample_path = r"d:\P\redrob\dataandai\India_runs_data_and_ai_challenge\sample_candidates.json"
    if not os.path.exists(sample_path):
        flash("Sample candidates file not found at " + sample_path, "danger")
        return redirect(url_for('main.upload_resumes'))
        
    try:
        with open(sample_path, 'r', encoding='utf-8') as f:
            candidates = json.load(f)
            
        # Clear existing candidates in DB
        Candidate.query.delete()
        Evaluation.query.delete()
        
        loaded = 0
        for cand in candidates:
            # Reconstruct raw_text for embedding
            skills_txt = ", ".join([s.get("name", "") for s in cand.get("skills", [])])
            jobs_txt = " ".join([f"{j.get('title')} at {j.get('company')}: {j.get('description')}" for j in cand.get("career_history", [])])
            edu_txt = " ".join([f"{e.get('degree')} in {e.get('field_of_study')} from {e.get('institution')}" for e in cand.get("education", [])])
            raw_text = f"{cand.get('profile', {}).get('headline')} {cand.get('profile', {}).get('summary')} Skills: {skills_txt}. Experience: {jobs_txt}. Education: {edu_txt}"
            
            c = Candidate(
                candidate_id=cand.get("candidate_id"),
                name=cand.get("profile", {}).get("anonymized_name"),
                email=f"{cand.get('candidate_id').lower()}@example.com",
                phone="9998887770",
                linkedin=f"linkedin.com/in/{cand.get('candidate_id').lower()}",
                github=f"github.com/{cand.get('candidate_id').lower()}",
                location=cand.get("profile", {}).get("location"),
                raw_text=raw_text
            )
            c.set_skills(cand.get("skills", []))
            c.set_career_history(cand.get("career_history", []))
            c.set_education(cand.get("education", []))
            c.set_certifications(cand.get("certifications", []))
            c.set_languages(cand.get("languages", []))
            c.set_redrob_signals(cand.get("redrob_signals", {}))
            
            db.session.add(c)
            loaded += 1
            
        db.session.commit()
        flash(f"Successfully loaded {loaded} candidates from sample pool!", "success")
    except Exception as e:
        flash(f"Error loading sample pool: {e}", "danger")
        
    return redirect(url_for('main.upload_resumes'))

@main_bp.route('/delete_candidate/<int:id>')
def delete_candidate(id):
    cand = Candidate.query.get_or_404(id)
    db.session.delete(cand)
    db.session.commit()
    flash(f"Deleted candidate {cand.name}.", "info")
    return redirect(url_for('main.upload_resumes'))

@main_bp.route('/processing')
def processing():
    job = JobDescription.query.first()
    if not job:
        return redirect(url_for('main.upload_jd'))
    candidates = Candidate.query.all()
    if not candidates:
        flash("Please upload resumes or load candidates pool first.", "warning")
        return redirect(url_for('main.upload_resumes'))
        
    return render_template('processing.html')

@main_bp.route('/run_pipeline')
def run_pipeline():
    """Trigger the ranking calculation asynchronously (AJAX endpoint)."""
    job = JobDescription.query.first()
    candidates = Candidate.query.all()
    
    if not job or not candidates:
        return jsonify({"status": "error", "message": "Missing job description or candidates."}), 400
        
    try:
        # Pre-load embedder instance (to cache model)
        Embedder.get_instance()
        
        # Convert candidates to dictionary format for ranking engine
        cand_list = []
        for c in candidates:
            # Create a dictionary mirroring the JSON schema
            skills_txt = ", ".join([s.get("name", "") for s in c.get_skills()])
            jobs_txt = " ".join([f"{j.get('title')} at {j.get('company')}: {j.get('description')}" for j in c.get_career_history()])
            edu_txt = " ".join([f"{e.get('degree')} in {e.get('field_of_study')} from {e.get('institution')}" for e in c.get_education()])
            raw_text = f"{c.name} headline: {c.raw_text} Skills: {skills_txt}. Experience: {jobs_txt}. Education: {edu_txt}"
            
            cand_dict = {
                "candidate_id": c.candidate_id,
                "profile": {
                    "anonymized_name": c.name,
                    "headline": "Candidate Profile",
                    "summary": c.raw_text[:400] if c.raw_text else "",
                    "location": c.location or "Unknown",
                    "years_of_experience": float(len(c.get_career_history()) * 2.0) or 5.0 # fallback
                },
                "career_history": c.get_career_history(),
                "education": c.get_education(),
                "skills": c.get_skills(),
                "certifications": c.get_certifications(),
                "redrob_signals": c.get_redrob_signals(),
                "raw_text": c.raw_text or raw_text
            }
            
            # Safely parse years of experience if available in signals or history
            years_exp = 5.0
            if c.raw_text and "Years Experience" in c.raw_text:
                try:
                    years_exp = float(c.raw_text.split("Years Experience")[0].split("-")[-1].strip())
                except:
                    pass
            elif c.get_redrob_signals():
                # Let's check if we can read exp from career history
                total_months = sum(j.get("duration_months", 0) for j in c.get_career_history())
                if total_months > 0:
                    years_exp = round(total_months / 12.0, 1)
            cand_dict["profile"]["years_of_experience"] = years_exp
            cand_list.append((c.id, cand_dict))
            
        # Run ranking engine
        # We unzip the list of tuples
        db_ids, dict_list = zip(*cand_list)
        results = rank_candidates(job, dict_list)
        
        # Save evaluations to DB
        Evaluation.query.delete() # clear old results
        
        for idx, res in enumerate(results):
            cand_db_id = db_ids[idx]
            eval_obj = Evaluation(
                job_id=job.id,
                candidate_id=cand_db_id,
                score_semantic=res["scores"]["semantic"],
                score_skills=res["scores"]["skills"],
                score_experience=res["scores"]["experience"],
                score_projects=res["scores"]["projects"],
                score_education=res["scores"]["education"],
                score_certifications=res["scores"]["certifications"],
                score_career_growth=res["scores"]["career_growth"],
                score_behavior=res["scores"]["behavior"],
                score_activity=res["scores"]["activity"],
                score_final=res["score_final"],
                recommendation=res["recommendation"]
            )
            eval_obj.set_explanation(res["explanation"])
            db.session.add(eval_obj)
            
        db.session.commit()
        
        # Calculate ranks after committing
        evaluations = Evaluation.query.order_by(Evaluation.score_final.desc()).all()
        # Tie break with candidate ID ascending
        eval_with_cid = []
        for e in evaluations:
            eval_with_cid.append((e, e.candidate.candidate_id if e.candidate else ""))
        eval_with_cid.sort(key=lambda x: (x[0].score_final, x[1]), reverse=True)
        # Note: we want score_final descending, but for identical scores, candidate_id ascending!
        # In Python: sort keys: score_final descending (-x[0].score_final), then x[1] ascending
        eval_with_cid.sort(key=lambda x: (-x[0].score_final, x[1]))
        
        for rank, (e, _) in enumerate(eval_with_cid, 1):
            e.rank = rank
            
        db.session.commit()
        return jsonify({"status": "success", "message": "Pipeline completed successfully!"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error running ranking pipeline: {e}"}), 500

@main_bp.route('/results')
def results():
    job = JobDescription.query.first()
    if not job:
        return redirect(url_for('main.upload_jd'))
        
    evaluations = Evaluation.query.order_by(Evaluation.rank.asc()).all()
    return render_template('results.html', evaluations=evaluations, job=job)

@main_bp.route('/details/<string:candidate_id>')
def details(candidate_id):
    job = JobDescription.query.first()
    candidate = Candidate.query.filter_by(candidate_id=candidate_id).first_or_404()
    evaluation = Evaluation.query.filter_by(candidate_id=candidate.id).first_or_404()
    
    # Safely load JSON structures for rendering
    skills = candidate.get_skills()
    career = candidate.get_career_history()
    education = candidate.get_education()
    certifications = candidate.get_certifications()
    signals = candidate.get_redrob_signals()
    explanation = evaluation.get_explanation()
    
    # Calculate years of experience
    years_exp = 5.0
    try:
        profile_dict = json.loads(candidate.raw_text) if candidate.raw_text.startswith('{') else {}
        years_exp = profile_dict.get("profile", {}).get("years_of_experience", 5.0)
    except:
        try:
            years_exp = float(candidate.raw_text.split("Years Experience")[0].split("-")[-1].strip())
        except:
            total_months = sum(j.get("duration_months", 0) for j in career)
            if total_months > 0:
                years_exp = round(total_months / 12.0, 1)

    return render_template(
        'details.html',
        job=job,
        candidate=candidate,
        evaluation=evaluation,
        skills=skills,
        career=career,
        education=education,
        certifications=certifications,
        signals=signals,
        explanation=explanation,
        years_exp=years_exp
    )

@main_bp.route('/dashboard')
def dashboard():
    job = JobDescription.query.first()
    if not job:
        flash("Please upload a Job Description first.", "warning")
        return redirect(url_for('main.upload_jd'))
        
    stats = get_dashboard_stats(job.id)
    return render_template('dashboard.html', stats=stats, job=job)

@main_bp.route('/download_excel')
def download_excel():
    job = JobDescription.query.first()
    if not job:
        flash("Job Description not found.", "danger")
        return redirect(url_for('main.index'))
        
    evaluations = Evaluation.query.order_by(Evaluation.rank.asc()).all()
    if not evaluations:
        flash("No evaluations to export. Please run the ranking pipeline first.", "warning")
        return redirect(url_for('main.upload_resumes'))
        
    # Convert evaluations to ranked dictionaries
    export_list = []
    for e in evaluations:
        cand = e.candidate
        export_list.append({
            "candidate_id": cand.candidate_id if cand else f"CAND_{e.candidate_id}",
            "name": cand.name if cand else "Unknown",
            "score_final": e.score_final,
            "scores": {
                "semantic": e.score_semantic,
                "skills": e.score_skills,
                "experience": e.score_experience,
                "projects": e.score_projects,
                "education": e.score_education,
                "certifications": e.score_certifications
            },
            "recommendation": e.recommendation,
            "explanation": e.get_explanation()
        })
        
    export_path = os.path.join(current_app.config['EXPORT_FOLDER'], 'ranked_candidates.xlsx')
    generate_excel_report(export_list, export_path)
    
    return send_file(export_path, as_attachment=True, download_name='ranked_candidates.xlsx')
