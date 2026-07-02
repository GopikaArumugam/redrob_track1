import json
from datetime import datetime
from config import Config
from utils.embedder import Embedder

# List of consulting firms to check for consulting-only career trap
CONSULTING_FIRMS = [
    'tcs', 'infosys', 'wipro', 'accenture', 'cognizant', 'capgemini',
    'tech mahindra', 'hcl', 'l&t', 'lnt', 'mindtree', 'mphasis', 'deloitte',
    'ey', 'kpmg', 'pwc', 'ibm'
]

def parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except:
        return None

def is_honeypot(cand_data):
    """
    Detect subtly impossible profiles in the candidate pool.
    Returns True if the candidate is a honeypot/trap, False otherwise.
    """
    career = cand_data.get("career_history", [])
    skills = cand_data.get("skills", [])
    education = cand_data.get("education", [])
    profile = cand_data.get("profile", {})
    
    # 1. Expert or Advanced skills with 0 months of experience
    zero_dur_skills = 0
    for s in skills:
        prof = s.get("proficiency", "").lower()
        dur = s.get("duration_months", 0)
        if prof in ["expert", "advanced"] and dur == 0:
            zero_dur_skills += 1
    if zero_dur_skills >= 4:
        return True, f"Honeypot: Claimed expert/advanced in {zero_dur_skills} skills with 0 months of experience."
        
    # 2. Claimed duration_months exceeds calendar months between start_date and end_date
    for job in career:
        start = parse_date(job.get("start_date"))
        end = parse_date(job.get("end_date"))
        dur_months = job.get("duration_months", 0)
        if start:
            # If end is null, assume present date
            end_date = end if end else datetime(2026, 7, 2)
            actual_months = (end_date.year - start.year) * 12 + (end_date.month - start.month)
            # Honeypots typically have huge mismatches (e.g. claiming 10 years at a 2-year job)
            if dur_months > actual_months + 48:
                return True, f"Honeypot: Claimed {dur_months} months at {job.get('company')} which only spanned {actual_months} calendar months."

    # 3. Graduation date and years of experience mismatch
    grad_years = []
    for edu in education:
        ey = edu.get("end_year")
        if ey:
            grad_years.append(ey)
    if grad_years:
        first_grad = min(grad_years)
        current_year = 2026
        max_possible_years = current_year - first_grad + 2 # Allow 2 years overlap
        years_exp = profile.get("years_of_experience", 0)
        if years_exp > max_possible_years + 5 and years_exp > 8:
            return True, f"Honeypot: Years of experience ({years_exp}) exceeds possible years post-graduation ({max_possible_years})."
            
    # 4. Total experience vs career history sum mismatch
    total_career_months = sum(job.get("duration_months", 0) for job in career)
    total_career_years = total_career_months / 12.0
    years_exp = profile.get("years_of_experience", 0)
    if abs(years_exp - total_career_years) > 15:
         return True, f"Honeypot: Total experience ({years_exp} yrs) has a severe mismatch with career history sum ({total_career_years:.1f} yrs)."

    return False, ""

def rank_candidates(job, candidates_list, weights=None):
    """
    Scoring engine that evaluates a list of candidates against a job description.
    job: JobDescription object or parsed dict
    candidates_list: List of Candidate objects or dicts
    weights: Configurable weights override
    """
    if weights is None:
        weights = Config.DEFAULT_WEIGHTS
        
    embedder = Embedder.get_instance()
    
    # 1. Parse JD if it's an object or dict
    if hasattr(job, 'raw_text'):
        jd_text = job.raw_text
        jd_skills = job.get_skills()
        jd_exp_req = job.experience_required
        jd_seniority = job.seniority
    else:
        jd_text = job.get("raw_text", "")
        jd_skills = job.get("skills", [])
        jd_exp_req = job.get("experience_required", 5.0)
        jd_seniority = job.get("seniority", "Senior")
        
    # Precompute JD embedding
    jd_emb = embedder.get_embedding(jd_text)
    
    evaluated_candidates = []
    
    for candidate in candidates_list:
        # Resolve objects vs dictionaries
        if hasattr(candidate, 'candidate_id'):
            cand_id = candidate.candidate_id
            name = candidate.name
            cand_skills = candidate.get_skills()
            career = candidate.get_career_history()
            education = candidate.get_education()
            certifications = candidate.get_certifications()
            signals = candidate.get_redrob_signals()
            raw_text = candidate.raw_text
            profile = json.loads(candidate.skills) if isinstance(candidate.skills, str) else candidate.skills # fallback
            profile_years_exp = candidate.get_redrob_signals().get("profile_completeness_score", 0) # dummy
            years_exp = 5.0 # fallback
            if hasattr(candidate, 'skills'):
                # load profile fields
                # In db Candidate model, profile is inside skills or stored in attributes
                # Let's map it safely
                try:
                    profile_dict = json.loads(candidate.raw_text) if candidate.raw_text.startswith('{') else {}
                except:
                    profile_dict = {}
            # Let's load the full candidate dictionary format if cached
            cand_dict = {
                "candidate_id": cand_id,
                "profile": {
                    "years_of_experience": 5.0,
                    "current_title": "Software Engineer"
                },
                "career_history": career,
                "education": education,
                "skills": cand_skills,
                "certifications": certifications,
                "redrob_signals": signals
            }
            # Try to get years_of_experience
            # Let's write a helper to safely parse Candidate objects
            try:
                # Let's load from candidate object methods
                years_exp = float(candidate.raw_text.split("Years Experience")[0].split("-")[-1].strip())
            except:
                years_exp = 5.0
        else:
            cand_dict = candidate
            cand_id = candidate.get("candidate_id")
            name = candidate.get("profile", {}).get("anonymized_name", "Anonymized")
            cand_skills = candidate.get("skills", [])
            career = candidate.get("career_history", [])
            education = candidate.get("education", [])
            certifications = candidate.get("certifications", [])
            signals = candidate.get("redrob_signals", {})
            raw_text = candidate.get("raw_text", "")
            years_exp = candidate.get("profile", {}).get("years_of_experience", 5.0)

        # ------------------ HONEYPOT CHECK ------------------
        is_hp, hp_reason = is_honeypot(cand_dict)
        if is_hp:
            # Penalize honeypots to zero
            evaluated_candidates.append({
                "candidate_id": cand_id,
                "name": name,
                "scores": {
                    "semantic": 0.0, "skills": 0.0, "experience": 0.0, "projects": 0.0,
                    "education": 0.0, "certifications": 0.0, "career_growth": 0.0,
                    "behavior": 0.0, "activity": 0.0
                },
                "score_final": 0.0,
                "recommendation": "Reject",
                "explanation": {
                    "strengths": [],
                    "gaps": ["Honeypot: Impossible profile data detected.", hp_reason],
                    "text": f"Profile data contains logical inconsistencies ({hp_reason}). Auto-disqualified by validation rules."
                }
            })
            continue

        # ------------------ 1. SEMANTIC MATCH SCORE (30%) ------------------
        # Build a resume text representation for embedding similarity
        resume_summary = ""
        if raw_text:
            resume_summary = raw_text
        else:
            # Reconstruct from JSON fields
            profile = cand_dict.get("profile", {})
            skills_txt = ", ".join([s.get("name", "") for s in cand_skills])
            jobs_txt = " ".join([f"{j.get('title')} at {j.get('company')}: {j.get('description')}" for j in career])
            edu_txt = " ".join([f"{e.get('degree')} in {e.get('field_of_study')} from {e.get('institution')}" for e in education])
            resume_summary = f"{profile.get('headline')} {profile.get('summary')} Skills: {skills_txt}. Experience: {jobs_txt}. Education: {edu_txt}"

        cand_emb = embedder.get_embedding(resume_summary)
        score_semantic = embedder.compute_similarity(jd_emb, cand_emb) * 100.0
        score_semantic = max(0.0, min(100.0, score_semantic))

        # ------------------ 2. SKILLS SCORE (25%) ------------------
        score_skills = 0.0
        if jd_skills:
            matched_weight = 0.0
            total_weight = 0.0
            
            # Map candidate skills for quick lookup
            cand_skills_map = {s.get("name", "").lower(): s for s in cand_skills}
            
            for jd_skill in jd_skills:
                jd_skill_lower = jd_skill.lower()
                weight = 1.0 # default skill weight
                total_weight += weight
                
                # Check for direct or synonym match
                matched = False
                prof_multiplier = 0.5 # default if matched but no prof
                
                if jd_skill_lower in cand_skills_map:
                    matched = True
                    prof = cand_skills_map[jd_skill_lower].get("proficiency", "intermediate").lower()
                    if prof == "expert":
                        prof_multiplier = 1.0
                    elif prof == "advanced":
                        prof_multiplier = 0.85
                    elif prof == "intermediate":
                        prof_multiplier = 0.65
                    else:
                        prof_multiplier = 0.40
                else:
                    # Synonym check
                    for c_skill_name, c_skill in cand_skills_map.items():
                        # Simple substring match
                        if jd_skill_lower in c_skill_name or c_skill_name in jd_skill_lower:
                            matched = True
                            prof = c_skill.get("proficiency", "intermediate").lower()
                            prof_multiplier = 0.60 # slightly lower multiplier for non-exact match
                            break
                            
                if matched:
                    matched_weight += weight * prof_multiplier
                    
            score_skills = (matched_weight / total_weight) * 100.0 if total_weight > 0 else 50.0
        else:
            score_skills = 60.0 # Default if no jd skills defined
        score_skills = min(100.0, score_skills)

        # ------------------ 3. EXPERIENCE SCORE (15%) ------------------
        score_experience = 100.0
        if years_exp < jd_exp_req:
            # Penalize under-experience
            score_experience = max(0.0, 100.0 - (jd_exp_req - years_exp) * 15.0)
        elif years_exp > jd_exp_req + 6.0:
            # Slight penalty for overqualification
            score_experience = max(80.0, 100.0 - (years_exp - (jd_exp_req + 6.0)) * 3.0)

        # Seniority Title Check
        current_title = cand_dict.get("profile", {}).get("current_title", "").lower()
        is_senior_role = any(kw in jd_seniority.lower() for kw in ["senior", "lead", "principal", "founding"])
        is_senior_candidate = any(kw in current_title for kw in ["senior", "lead", "manager", "principal", "architect", "head", "vp"])
        
        if is_senior_role and not is_senior_candidate:
            # Apply junior-title penalty for senior role
            score_experience = max(40.0, score_experience - 20.0)

        # ------------------ 4. PROJECTS SCORE (10%) ------------------
        score_projects = 50.0
        project_descriptions = []
        for job in career:
            desc = job.get("description", "")
            if desc:
                project_descriptions.append(desc)
        
        if project_descriptions:
            proj_text = " ".join(project_descriptions)
            proj_emb = embedder.get_embedding(proj_text)
            # Compare project description with JD requirements
            score_projects = embedder.compute_similarity(jd_emb, proj_emb) * 100.0
            score_projects = max(0.0, min(100.0, score_projects))
            # Boost if projects mention RAG, vector search, or ML models
            proj_text_lower = proj_text.lower()
            if any(kw in proj_text_lower for kw in ["rag", "vector search", "milvus", "qdrant", "pinecone", "embeddings", "faiss"]):
                score_projects = min(100.0, score_projects + 10.0)

        # ------------------ 5. EDUCATION SCORE (5%) ------------------
        # Degree weight: PhD = 100, MS = 90, BE/BTech = 80, others = 60
        # Tier weight: tier_1 = 100, tier_2 = 85, tier_3 = 70, tier_4 = 60, unknown = 50
        degree_score = 70.0
        tier_score = 50.0
        
        for edu in education:
            deg = edu.get("degree", "").lower()
            tier = edu.get("tier", "").lower()
            
            # Degree matching
            if "ph.d" in deg or "phd" in deg:
                degree_score = max(degree_score, 100.0)
            elif "master" in deg or "m.s" in deg or "ms" in deg or "m.tech" in deg or "m.e" in deg or "mba" in deg:
                degree_score = max(degree_score, 90.0)
            elif "bachelor" in deg or "b.s" in deg or "bs" in deg or "b.tech" in deg or "b.e" in deg or "be" in deg:
                degree_score = max(degree_score, 80.0)
                
            # Tier matching
            if tier == "tier_1":
                tier_score = max(tier_score, 100.0)
            elif tier == "tier_2":
                tier_score = max(tier_score, 85.0)
            elif tier == "tier_3":
                tier_score = max(tier_score, 70.0)
            elif tier == "tier_4":
                tier_score = max(tier_score, 60.0)
                
        score_education = 0.6 * degree_score + 0.4 * tier_score

        # ------------------ 6. CERTIFICATIONS SCORE (5%) ------------------
        score_certifications = 0.0
        cert_names = [c.get("name", "").lower() for c in certifications]
        if cert_names:
            relevant_certs = 0
            for name in cert_names:
                if any(kw in name for kw in ["aws", "cloud", "tensorflow", "pytorch", "gcp", "azure", "machine learning", "deep learning", "kubernetes", "faiss"]):
                    relevant_certs += 1
            score_certifications = min(100.0, 40.0 + relevant_certs * 30.0)
        else:
            # If no certifications, check if they have strong skills and give them a baseline score
            score_certifications = 50.0 if score_skills > 70.0 else 30.0

        # ------------------ 7. CAREER GROWTH SCORE (5%) ------------------
        # Evaluate title progression
        score_career_growth = 70.0
        title_levels = []
        for job in career:
            title = job.get("title", "").lower()
            lvl = 2 # default engineer level
            if any(kw in title for kw in ["intern", "junior", "trainee", "associate"]):
                lvl = 1
            elif any(kw in title for kw in ["senior", "sr."]):
                lvl = 3
            elif any(kw in title for kw in ["lead", "manager", "coordinator"]):
                lvl = 4
            elif any(kw in title for kw in ["principal", "architect", "director", "head", "vp"]):
                lvl = 5
            title_levels.append(lvl)
            
        # Reverse to chronological order (usually resume JSON history starts with current job)
        title_levels.reverse()
        if len(title_levels) >= 2:
            # Check if levels are generally increasing
            increases = sum(1 for i in range(len(title_levels)-1) if title_levels[i+1] > title_levels[i])
            decreases = sum(1 for i in range(len(title_levels)-1) if title_levels[i+1] < title_levels[i])
            if increases > 0 and decreases == 0:
                score_career_growth = 100.0
            elif increases > decreases:
                score_career_growth = 85.0
            elif decreases > increases:
                score_career_growth = 50.0
                
        # Apply Title-Chaser Penalty
        # Switching companies too often (e.g. average tenure less than 18 months / 1.5 years)
        if len(career) >= 3:
            total_tenure_months = sum(job.get("duration_months", 0) for job in career)
            avg_tenure_years = (total_tenure_months / len(career)) / 12.0
            if avg_tenure_years < 1.5:
                # Title chaser penalty
                score_career_growth = max(30.0, score_career_growth - 30.0)

        # ------------------ 8. BEHAVIOR SCORE (3%) ------------------
        # Based on availability, response rates, and notice periods
        resp_rate = signals.get("recruiter_response_rate", 0.70)
        completion_rate = signals.get("interview_completion_rate", 0.80)
        open_to_work = signals.get("open_to_work_flag", True)
        avg_resp_time = signals.get("avg_response_time_hours", 24.0)
        
        otw_score = 100.0 if open_to_work else 50.0
        time_score = 100.0 if avg_resp_time < 12.0 else (70.0 if avg_resp_time < 24.0 else 40.0)
        
        score_behavior = (resp_rate * 40.0) + (completion_rate * 30.0) + (otw_score * 0.20) + (time_score * 0.10)
        score_behavior = max(0.0, min(100.0, score_behavior))

        # ------------------ 9. ACTIVITY SCORE (2%) ------------------
        # Based on platform activity, connections, GitHub, and email/phone verification
        gh_score = signals.get("github_activity_score", -1)
        if gh_score == -1:
            gh_score = 40.0 # baseline if no github
            
        profile_completeness = signals.get("profile_completeness_score", 80.0)
        saved_rec = signals.get("saved_by_recruiters_30d", 0)
        saved_score = min(100.0, saved_rec * 15.0)
        
        score_activity = (gh_score * 0.40) + (profile_completeness * 0.30) + (saved_score * 0.30)
        score_activity = max(0.0, min(100.0, score_activity))

        # ------------------ TRAPS & QUALIFICATION PENALTIES ------------------
        qualification_multiplier = 1.0
        penalties_applied = []
        
        # 1. Consulting-only Career Penalty
        # Check if all jobs in career history are at consulting firms
        if career:
            consulting_jobs = 0
            for job in career:
                company_lower = job.get("company", "").lower()
                if any(firm in company_lower for firm in CONSULTING_FIRMS):
                    consulting_jobs += 1
            if consulting_jobs == len(career):
                qualification_multiplier *= 0.50 # Reduce score by 50%
                penalties_applied.append("Career consists entirely of consulting companies (IT services).")

        # 2. Pure Research-only Career Penalty
        if career:
            research_jobs = 0
            for job in career:
                desc = job.get("description", "").lower()
                title = job.get("title", "").lower()
                if any(kw in title or kw in desc for kw in ["research assistant", "academic lab", "postdoc", "phd scholar", "fellow"]):
                    research_jobs += 1
            if research_jobs == len(career) and "phd" in [edu.get("degree", "").lower() for edu in education]:
                qualification_multiplier *= 0.60 # Reduce by 40%
                penalties_applied.append("Career resides strictly in academic/research environments with no production deployment.")

        # 3. Junior Location / Relocation penalty (JD is Noida/Pune hybrid)
        location_lower = cand_dict.get("profile", {}).get("location", "").lower()
        willing_relocate = signals.get("willing_to_relocate", True)
        is_local = any(loc in location_lower for loc in Config.TARGET_LOCATIONS)
        if not is_local and not willing_relocate:
            qualification_multiplier *= 0.70 # Reduce by 30%
            penalties_applied.append("Candidate is located outside target hubs and is unwilling to relocate.")

        # ------------------ AGGREGATE FINAL SCORE ------------------
        score_final = (
            score_semantic * weights['semantic'] +
            score_skills * weights['skills'] +
            score_experience * weights['experience'] +
            score_projects * weights['projects'] +
            score_education * weights['education'] +
            score_certifications * weights['certifications'] +
            score_career_growth * weights['career_growth'] +
            score_behavior * weights['behavior'] +
            score_activity * weights['activity']
        )
        
        # Apply qualification multipliers
        score_final *= qualification_multiplier
        score_final = round(max(0.0, min(100.0, score_final)), 2)

        # ------------------ RECOMMENDATION ENGINE ------------------
        recommendation = "Reject"
        if score_final >= Config.THRESHOLD_STRONG_HIRE:
            recommendation = "Strong Hire"
        elif score_final >= Config.THRESHOLD_HIRE:
            recommendation = "Hire"
        elif score_final >= Config.THRESHOLD_CONSIDER:
            recommendation = "Consider"

        # ------------------ EXPLAINABLE AI GENERATION ------------------
        strengths = []
        gaps = []
        
        # Determine Strengths
        if score_semantic > 75:
            strengths.append(f"Excellent semantic alignment ({score_semantic:.1f}%) with job description responsibilities.")
        if score_skills > 75:
            strengths.append("Matches core required technologies with advanced/expert proficiency.")
        if years_exp >= jd_exp_req:
            strengths.append(f"Meets or exceeds the required experience bracket with {years_exp} years.")
        if score_career_growth > 80:
            strengths.append("Demonstrates positive, stable career progression with upward title trajectory.")
        if signals.get("github_activity_score", 0) > 60:
            strengths.append("High GitHub contribution metrics indicating active development practice.")
        if signals.get("recruiter_response_rate", 0) > 0.85:
            strengths.append("Exceptional platform responsiveness and interview completion history.")

        # Determine Gaps
        if score_semantic < 55:
            gaps.append("Low semantic match to the core job details.")
        if score_skills < 50:
            gaps.append("Missing multiple primary skills requested in the job description.")
        if years_exp < jd_exp_req:
            gaps.append(f"Has {years_exp} years of experience, which is below the required {jd_exp_req} years.")
        if score_career_growth < 50:
            gaps.append("High frequency of company switching (under 1.5 years tenure) indicating potential flight risk.")
        for penalty in penalties_applied:
            gaps.append(penalty)

        # 1-2 Sentence Reasoning Summary (Perfect for Hackathon reasoning column)
        skills_matched_list = [s.get("name") for s in cand_skills if s.get("name") in jd_skills][:3]
        skills_str = ", ".join(skills_matched_list) if skills_matched_list else "core tech stack"
        
        if is_hp:
             reasoning_text = f"Invalid profile data detected: {hp_reason}"
        elif score_final >= Config.THRESHOLD_STRONG_HIRE:
             reasoning_text = f"Top-tier Candidate with {years_exp} years experience. Exceptional match for {skills_str}. Strong career trajectory at product companies and solid behavioral signals."
        elif score_final >= Config.THRESHOLD_HIRE:
             reasoning_text = f"Qualified Candidate with {years_exp} years experience. Solid alignment with {skills_str} and good project portfolio, though some minor skill gaps or notice period constraints exist."
        elif score_final >= Config.THRESHOLD_CONSIDER:
             reasoning_text = f"Borderline Candidate. Has relevant experience in {skills_str} but shows lower semantic match, high company switching, or consulting-heavy career trajectory."
        else:
             reasoning_text = f"Unsuitable Candidate. Mismatch in experience levels, poor skill alignment, or failed essential qualification filters (e.g. consulting-only or research-only background)."

        explanation_dict = {
            "strengths": strengths,
            "gaps": gaps,
            "text": reasoning_text
        }

        evaluated_candidates.append({
            "candidate_id": cand_id,
            "name": name,
            "scores": {
                "semantic": round(score_semantic, 2),
                "skills": round(score_skills, 2),
                "experience": round(score_experience, 2),
                "projects": round(score_projects, 2),
                "education": round(score_education, 2),
                "certifications": round(score_certifications, 2),
                "career_growth": round(score_career_growth, 2),
                "behavior": round(score_behavior, 2),
                "activity": round(score_activity, 2)
            },
            "score_final": score_final,
            "recommendation": recommendation,
            "explanation": explanation_dict
        })
        
    return evaluated_candidates
