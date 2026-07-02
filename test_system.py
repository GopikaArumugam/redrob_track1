import os
import sys
import unittest
import numpy as np

# Add root to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.parser import parse_job_description_text, extract_skills_from_text, parse_experience_years
from utils.embedder import Embedder, FaissSearchIndex
from utils.ranker import is_honeypot, rank_candidates
from utils.exporter import generate_excel_report

class TestAIRecruiterSystem(unittest.TestCase):
    
    def setUp(self):
        # Sample clean candidate data
        self.mock_candidate = {
            "candidate_id": "CAND_1111111",
            "profile": {
                "anonymized_name": "John Doe",
                "headline": "Senior AI Engineer",
                "summary": "Building production RAG and vector search pipelines for 6 years.",
                "location": "Pune",
                "years_of_experience": 6.5
            },
            "career_history": [
                {
                    "company": "Tech Product Inc",
                    "title": "Senior Machine Learning Engineer",
                    "start_date": "2021-01-01",
                    "end_date": None,
                    "duration_months": 66,
                    "is_current": True,
                    "description": "Deployed vector databases and fine-tuned transformers."
                }
            ],
            "education": [
                {
                    "institution": "IIT Bombay",
                    "degree": "M.Tech",
                    "field_of_study": "Computer Science",
                    "end_year": 2020,
                    "tier": "tier_1"
                }
            ],
            "skills": [
                {"name": "Python", "proficiency": "expert", "duration_months": 72},
                {"name": "PyTorch", "proficiency": "advanced", "duration_months": 48},
                {"name": "FAISS", "proficiency": "advanced", "duration_months": 24}
            ],
            "certifications": [
                {"name": "AWS Certified Machine Learning", "issuer": "Amazon", "year": 2024}
            ],
            "redrob_signals": {
                "profile_completeness_score": 95.0,
                "recruiter_response_rate": 0.85,
                "notice_period_days": 30,
                "willing_to_relocate": True,
                "github_activity_score": 75.0,
                "open_to_work_flag": True
            }
        }
        
        # Sample honeypot candidate (impossible date mismatch)
        self.mock_honeypot = {
            "candidate_id": "CAND_9999999",
            "profile": {
                "anonymized_name": "Fake Profile",
                "headline": "Expert AI Developer",
                "years_of_experience": 15.0
            },
            "career_history": [
                {
                    "company": "Small Corp",
                    "title": "Developer",
                    "start_date": "2024-01-01",
                    "end_date": "2026-01-01",
                    "duration_months": 180, # Claiming 15 years in a 2-year job!
                    "is_current": False,
                    "description": "Impossible duration."
                }
            ],
            "education": [
                {
                    "institution": "College",
                    "degree": "B.E.",
                    "end_year": 2023,
                    "tier": "tier_4"
                }
            ],
            "skills": [
                {"name": "Python", "proficiency": "expert", "duration_months": 0} # 0 duration expert
            ],
            "certifications": [],
            "redrob_signals": {
                "profile_completeness_score": 80.0,
                "recruiter_response_rate": 0.90,
                "notice_period_days": 30,
                "willing_to_relocate": True
            }
        }

        # Mock Job Description
        self.mock_job = {
            "title": "Senior AI Engineer",
            "experience_required": 5.0,
            "skills": ["Python", "PyTorch", "FAISS", "AWS"],
            "location": "Pune/Noida, India",
            "seniority": "Senior",
            "raw_text": "We need a Senior AI Engineer with Python and 5+ years experience building RAG systems and vector search databases like FAISS."
        }

    def test_parser(self):
        """Test parsing heuristics and skills extraction."""
        jd_parsed = parse_job_description_text(self.mock_job["raw_text"])
        self.assertEqual(jd_parsed["experience_required"], 5.0)
        self.assertIn("Python", jd_parsed["skills"])
        self.assertIn("FAISS", jd_parsed["skills"])
        
        extracted_skills = extract_skills_from_text("Experience with AWS and Docker containers.")
        skills_list = [s["name"] for s in extracted_skills]
        self.assertIn("AWS", skills_list)
        self.assertIn("Docker", skills_list)

        exp_years = parse_experience_years("6.9 years of experience in data science.")
        self.assertEqual(exp_years, 6.9)

    def test_embedder(self):
        """Test SentenceTransformer embeddings and FAISS index."""
        embedder = Embedder.get_instance()
        emb1 = embedder.get_embedding("Senior AI Engineer Python")
        emb2 = embedder.get_embedding("Senior AI Engineer Python")
        emb3 = embedder.get_embedding("Accounting Manager Finance")
        
        self.assertEqual(emb1.shape, (384,))
        
        # Test similarity
        sim_same = embedder.compute_similarity(emb1, emb2)
        sim_diff = embedder.compute_similarity(emb1, emb3)
        self.assertAlmostEqual(sim_same, 1.0, places=4)
        self.assertTrue(sim_same > sim_diff)

        # Test FAISS
        faiss_idx = FaissSearchIndex(dimension=384)
        faiss_idx.add_candidates(["CAND_1"], [emb1])
        faiss_idx.add_candidates(["CAND_2"], [emb3])
        
        results = faiss_idx.query(emb2, k=2)
        self.assertEqual(results[0][0], "CAND_1")
        self.assertTrue(results[0][1] > results[1][1])

    def test_honeypot_detector(self):
        """Test that the honeypot detector flags fake profiles."""
        is_hp_clean, reason_clean = is_honeypot(self.mock_candidate)
        is_hp_trap, reason_trap = is_honeypot(self.mock_honeypot)
        
        self.assertFalse(is_hp_clean)
        self.assertTrue(is_hp_trap)
        self.assertIn("Claimed 180 months", reason_trap)

    def test_ranker(self):
        """Test candidate ranking math and reasoning outputs."""
        results = rank_candidates(self.mock_job, [self.mock_candidate, self.mock_honeypot])
        
        self.assertEqual(len(results), 2)
        
        # Clean candidate should score highly, honeypot should score 0
        clean_res = next(r for r in results if r["candidate_id"] == "CAND_1111111")
        trap_res = next(r for r in results if r["candidate_id"] == "CAND_9999999")
        
        self.assertTrue(clean_res["score_final"] > 60.0)
        self.assertEqual(trap_res["score_final"], 0.0)
        self.assertEqual(trap_res["recommendation"], "Reject")
        self.assertIn("Honeypot", trap_res["explanation"]["gaps"][0])

    def test_exporter(self):
        """Test Excel sheet generation."""
        dummy_results = [{
            "candidate_id": "CAND_1111111",
            "name": "John Doe",
            "score_final": 88.5,
            "scores": {
                "semantic": 90.0, "skills": 85.0, "experience": 100.0,
                "projects": 80.0, "education": 90.0, "certifications": 100.0
            },
            "recommendation": "Strong Hire",
            "explanation": {"text": "Excellent match."}
        }]
        out_path = "test_export.xlsx"
        try:
            generate_excel_report(dummy_results, out_path)
            self.assertTrue(os.path.exists(out_path))
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

if __name__ == "__main__":
    unittest.main()
