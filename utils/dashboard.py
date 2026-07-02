from collections import Counter
import json
from database import Candidate, Evaluation, JobDescription

def get_dashboard_stats(job_id=None):
    """
    Calculates overall statistics and data distributions for Chart.js from the database.
    """
    # 1. Fetch evaluations
    query = Evaluation.query
    if job_id:
        query = query.filter_by(job_id=job_id)
        
    evaluations = query.all()
    
    if not evaluations:
        return {
            "total_candidates": 0,
            "avg_score": 0.0,
            "avg_experience": 0.0,
            "reco_counts": {"Strong Hire": 0, "Hire": 0, "Consider": 0, "Reject": 0},
            "top_skills": [],
            "score_distribution": {"labels": ["<50", "50-69", "70-84", "85+"], "data": [0, 0, 0, 0]},
            "exp_distribution": {"labels": ["0-2 Yrs", "3-5 Yrs", "6-8 Yrs", "9+ Yrs"], "data": [0, 0, 0, 0]},
            "top_candidates": []
        }
        
    total_candidates = len(evaluations)
    total_score = sum(e.score_final for e in evaluations)
    avg_score = round(total_score / total_candidates, 2)
    
    # Calculate average experience
    total_exp = 0.0
    valid_exp_candidates = 0
    
    # Recommendation counts
    reco_counts = {"Strong Hire": 0, "Hire": 0, "Consider": 0, "Reject": 0}
    
    # Score distribution bands
    score_bands = [0, 0, 0, 0] # <50, 50-69, 70-84, 85+
    
    # Experience distribution bands
    exp_bands = [0, 0, 0, 0] # 0-2, 3-5, 6-8, 9+
    
    all_skills = []
    top_cands = []
    
    for eval_obj in evaluations:
        cand = eval_obj.candidate
        
        # Parse candidate skills
        cand_skills = cand.get_skills() if cand else []
        for s in cand_skills:
            all_skills.append(s.get("name"))
            
        # Parse experience
        cand_exp = 5.0 # default fallback
        if cand:
            try:
                # Load profile details
                profile_dict = json.loads(cand.raw_text) if cand.raw_text.startswith('{') else {}
                cand_exp = profile_dict.get("profile", {}).get("years_of_experience", 5.0)
            except:
                # Fallback to headline parse
                try:
                    cand_exp = float(cand.raw_text.split("Years Experience")[0].split("-")[-1].strip())
                except:
                    pass
            total_exp += cand_exp
            valid_exp_candidates += 1
            
            # Experience bands
            if cand_exp <= 2.0:
                exp_bands[0] += 1
            elif cand_exp <= 5.0:
                exp_bands[1] += 1
            elif cand_exp <= 8.0:
                exp_bands[2] += 1
            else:
                exp_bands[3] += 1
                
        # Recommendation
        rec = eval_obj.recommendation
        if rec in reco_counts:
            reco_counts[rec] += 1
            
        # Score bands
        sc = eval_obj.score_final
        if sc < 50.0:
            score_bands[0] += 1
        elif sc < 70.0:
            score_bands[1] += 1
        elif sc < 85.0:
            score_bands[2] += 1
        else:
            score_bands[3] += 1
            
        # Add to list for sorting top candidates
        top_cands.append({
            "candidate_id": cand.candidate_id if cand else f"CAND_{eval_obj.candidate_id}",
            "name": cand.name if cand else "Unknown",
            "score": eval_obj.score_final,
            "recommendation": eval_obj.recommendation
        })
        
    avg_experience = round(total_exp / valid_exp_candidates, 1) if valid_exp_candidates > 0 else 0.0
    
    # Skills counts
    skills_counter = Counter(all_skills)
    top_skills = [{"name": name, "count": count} for name, count in skills_counter.most_common(8)]
    
    # Sort top candidates
    top_cands.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = top_cands[:5]
    
    return {
        "total_candidates": total_candidates,
        "avg_score": avg_score,
        "avg_experience": avg_experience,
        "reco_counts": reco_counts,
        "top_skills": top_skills,
        "score_distribution": {
            "labels": ["<50 (Reject)", "50-69 (Consider)", "70-84 (Hire)", "85+ (Strong Hire)"],
            "data": score_bands
        },
        "exp_distribution": {
            "labels": ["Junior (0-2 Yrs)", "Mid (3-5 Yrs)", "Senior (6-8 Yrs)", "Lead/Principal (9+ Yrs)"],
            "data": exp_bands
        },
        "top_candidates": top_candidates
    }
