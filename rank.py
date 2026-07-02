import os
import sys
import json
import csv
import gzip
import argparse
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

# Import utils modules by adding root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.parser import parse_job_description_text, SKILL_MAP
from utils.ranker import rank_candidates, is_honeypot
from utils.embedder import Embedder

FALLBACK_JD_TEXT = """
Job Description: Senior AI Engineer – Founding Team
Company: Redrob AI (Series A AI-native talent intelligence platform)
Location: Pune/Noida, India (Hybrid – flexible cadence) | Open to relocation candidates from Tier-1 Indian cities
Employment Type: Full-time
Experience Required: 5–9 years

What we actually need:
- Deep technical depth in modern ML systems – embeddings, retrieval, ranking, LLMs, fine-tuning.
- Production experience with embeddings-based retrieval systems (sentence-transformers, OpenAI embeddings, BGE, E5, or similar) deployed to real users.
- Production experience with vector databases or hybrid search infrastructure – Pinecone, Weaviate, Qdrant, Milvus, OpenSearch, Elasticsearch, FAISS, or something similar.
- Strong Python. Yes really, we care about code quality.
- Hands-on experience designing evaluation frameworks for ranking systems – NDCG, MRR, MAP, offline-to-online correlation, A/B test interpretation.

Disqualifiers:
- Career entirely in pure research environments without production deployment.
- AI experience consists primarily of recent (under 12 months) projects using LangChain to call OpenAI.
- Senior engineer who hasn't written production code in the last 18 months.
- Title-chasers switching companies every 1.5 years or less.
- People who have only worked at consulting firms (TCS, Infosys, Wipro, Accenture, Cognizant, Capgemini, etc.) in their entire career.
- Primary expertise is computer vision, speech, or robotics without significant NLP/IR exposure.
"""

def read_docx(file_path):
    try:
        if not os.path.exists(file_path):
            return None
        with zipfile.ZipFile(file_path) as z:
            xml_content = z.read('word/document.xml')
            root = ET.fromstring(xml_content)
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            texts = []
            for paragraph in root.findall('.//w:p', ns):
                p_text = []
                for run in paragraph.findall('.//w:t', ns):
                    if run.text:
                        p_text.append(run.text)
                if p_text:
                    texts.append("".join(p_text))
            return "\n".join(texts)
    except Exception as e:
        print(f"Warning: Could not parse docx {file_path}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Rank candidates for Senior AI Engineer.")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl (or .gz)")
    parser.add_argument("--out", required=True, help="Path to output submission.csv")
    args = parser.parse_args()

    print("=== Starting Ranking Pipeline ===")
    
    # 1. Load Job Description
    jd_text = None
    # Check potential paths for job_description.docx
    paths_to_check = [
        "job_description.docx",
        "job_description.txt",
        "job_description.md",
        os.path.join("dataandai", "India_runs_data_and_ai_challenge", "job_description.docx"),
        os.path.join("dataandai", "India_runs_data_and_ai_challenge", "job_description.txt")
    ]
    
    for p in paths_to_check:
        if os.path.exists(p):
            if p.endswith(".docx"):
                jd_text = read_docx(p)
            else:
                with open(p, "r", encoding="utf-8") as f:
                    jd_text = f.read()
            if jd_text:
                print(f"Loaded Job Description from: {p}")
                break
                
    if not jd_text:
        print("Using built-in fallback Job Description...")
        jd_text = FALLBACK_JD_TEXT

    parsed_jd = parse_job_description_text(jd_text)
    
    # Pre-warm embedder (downloads weights if not cached)
    print("Initializing embedding model...")
    embedder = Embedder.get_instance()
    
    # 2. Stage 1 Retrieval: Fast screening of 100k candidates
    print(f"Reading candidates from {args.candidates}...")
    candidates_pool = []
    
    # Determine file opening method
    is_gz = args.candidates.endswith(".gz")
    open_func = gzip.open if is_gz else open
    mode = "rt" if is_gz else "r"
    
    # Highly specialized AI/ML search terms matching the specific Senior AI Engineer JD
    ai_ml_keywords = {
        "embeddings", "vector database", "vector search", "faiss", "milvus", 
        "qdrant", "pinecone", "weaviate", "rag", "ndcg", "mrr", "map", 
        "learning to rank", "hybrid search"
    }

    # Consulting firms to exclude
    CONSULTING_FIRMS = [
        'tcs', 'infosys', 'wipro', 'accenture', 'cognizant', 'capgemini',
        'tech mahindra', 'hcl', 'l&t', 'lnt', 'mindtree', 'mphasis', 'deloitte',
        'ey', 'kpmg', 'pwc', 'ibm'
    ]

    def is_consulting_only(c):
        career_list = c.get("career_history", [])
        if not career_list:
            return False
        c_count = 0
        for job in career_list:
            comp_lower = job.get("company", "").lower()
            if any(firm in comp_lower for firm in CONSULTING_FIRMS):
                c_count += 1
        return c_count == len(career_list)

    count = 0
    with open_func(args.candidates, mode, encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            count += 1
            cand = json.loads(line)
            
            # 1. Fast Honeypot check - discard immediately
            is_hp, _ = is_honeypot(cand)
            if is_hp:
                continue
                
            # 2. Experience check - JD is 5-9 years, require at least 5.0 years
            years_exp = cand.get("profile", {}).get("years_of_experience", 5.0)
            if years_exp < 5.0:
                continue
                
            # 3. Exclude consulting-only careers (explicit disqualifier in JD)
            if is_consulting_only(cand):
                continue
                
            # 4. Location/Relocation check
            location = cand.get("profile", {}).get("location", "").lower()
            willing_relocate = cand.get("redrob_signals", {}).get("willing_to_relocate", True)
            is_local = any(loc in location for loc in ["noida", "pune", "delhi", "hyderabad", "mumbai", "bangalore"])
            if not is_local and not willing_relocate:
                continue

            # 5. Activity checks - reject inactive profiles
            signals = cand.get("redrob_signals", {})
            if signals.get("recruiter_response_rate", 1.0) < 0.50:
                continue
            if signals.get("profile_completeness_score", 100) < 40:
                continue
                
            # 6. Notice Period check (JD requests sub-30-day, but up to 60-day is acceptable)
            if signals.get("notice_period_days", 30) > 60:
                continue
                
            # 7. Core NLP/ML keyword screening
            headline = cand.get("profile", {}).get("headline", "").lower()
            summary = cand.get("profile", {}).get("summary", "").lower()
            skills = [s.get("name", "").lower() for s in cand.get("skills", [])]
            
            skills_txt = " ".join(skills)
            search_space = f"{headline} {summary} {skills_txt}"
            
            # Check overlap with ML keywords
            has_keyword = any(kw in search_space for kw in ai_ml_keywords)
            if not has_keyword:
                continue
                
            # Pass all filters: candidate enters Stage 2 Ranking
            candidates_pool.append(cand)
            
    print(f"Scanned {count} candidates. Retrieved {len(candidates_pool)} eligible candidates for deep ML ranking.")
    
    # 3. Stage 2 Deep ML Ranking
    print("Running multi-signal scoring model...")
    scored_candidates = rank_candidates(parsed_jd, candidates_pool)
    
    # Sort candidates by final score descending
    # In case of tie, sort by candidate_id ascending
    scored_candidates.sort(key=lambda x: (-x["score_final"], x["candidate_id"]))
    
    # Take top 100
    top_100 = scored_candidates[:100]
    
    # Pad with filler if less than 100 (highly unlikely in a pool of 100k)
    if len(top_100) < 100:
        print(f"Warning: Only {len(top_100)} candidates passed pre-filters. Padding list...")
        # Add back some candidates that were filtered out
        # We can implement a simple fallback if needed
        
    print(f"Writing top 100 results to {args.out}...")
    
    # Ensure directory exists
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    with open(args.out, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        # Header
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for idx, cand in enumerate(top_100, 1):
            writer.writerow([
                cand["candidate_id"],
                idx,
                cand["score_final"],
                cand["explanation"]["text"]
            ])
            
    print("=== Pipeline Completed Successfully! ===")

if __name__ == "__main__":
    main()
