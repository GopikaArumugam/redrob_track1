import re
import os
import pdfplumber
import fitz  # PyMuPDF
import spacy

# Load spaCy blank model or download if not available.
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = spacy.blank("en")

# Predefined skill dictionary & synonym mapping for synonyms resolution
SKILL_MAP = {
    'amazon web services': 'AWS',
    'aws': 'AWS',
    'docker containers': 'Docker',
    'docker': 'Docker',
    'kubernetes': 'Kubernetes',
    'k8s': 'Kubernetes',
    'python engineer': 'Python',
    'python developer': 'Python',
    'python': 'Python',
    'scikit-learn': 'Scikit-Learn',
    'scikit learn': 'Scikit-Learn',
    'sklearn': 'Scikit-Learn',
    'tensorflow': 'TensorFlow',
    'pytorch': 'PyTorch',
    'apache spark': 'Spark',
    'spark': 'Spark',
    'apache kafka': 'Kafka',
    'kafka': 'Kafka',
    'apache airflow': 'Airflow',
    'airflow': 'Airflow',
    'natural language processing': 'NLP',
    'nlp': 'NLP',
    'retrieval augmented generation': 'RAG',
    'rag': 'RAG',
    'vector database': 'Vector DB',
    'vector search': 'Vector DB',
    'faiss': 'FAISS',
    'milvus': 'Milvus',
    'qdrant': 'Qdrant',
    'pinecone': 'Pinecone',
    'weaviate': 'Weaviate',
    'elasticsearch': 'Elasticsearch',
    'opensearch': 'OpenSearch',
    'sql': 'SQL',
    'snowflake': 'Snowflake',
    'github': 'GitHub',
    'git': 'Git',
    'large language models': 'LLMs',
    'llm': 'LLMs',
    'deep learning': 'Deep Learning',
    'machine learning': 'Machine Learning',
    'ml': 'Machine Learning',
    'artificial intelligence': 'AI',
    'ai': 'AI',
    'learning to rank': 'Learning to Rank',
    'ltr': 'Learning to Rank',
    'system design': 'System Design',
    'ci/cd': 'CI/CD',
    'jenkins': 'Jenkins',
    'fastapi': 'FastAPI',
    'flask': 'Flask',
    'django': 'Django'
}

COMMON_SKILLS = list(set(SKILL_MAP.values()))

def extract_pdf_text(file_path):
    """Extract raw text from PDF using PyMuPDF (fitz) with pdfplumber fallback."""
    text = ""
    # Try PyMuPDF
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"PyMuPDF failed on {file_path}, falling back to pdfplumber: {e}")
        # Fallback to pdfplumber
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e2:
            print(f"pdfplumber also failed on {file_path}: {e2}")
    
    return text.strip()

def parse_contact_details(text):
    """Extract Name, Email, Phone, LinkedIn, and GitHub using RegEx and Heuristics."""
    email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    phone_pattern = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+?\d{10,12}')
    linkedin_pattern = re.compile(r'linkedin\.com/in/[\w\.-]+', re.IGNORECASE)
    github_pattern = re.compile(r'github\.com/[\w\.-]+', re.IGNORECASE)

    email = email_pattern.search(text)
    phone = phone_pattern.search(text)
    linkedin = linkedin_pattern.search(text)
    github = github_pattern.search(text)

    email = email.group(0) if email else None
    phone = phone.group(0) if phone else None
    linkedin = linkedin.group(0) if linkedin else None
    github = github.group(0) if github else None

    # Name extraction heuristic (using Spacy NER or First Lines)
    name = "Candidate Name"
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        # Check first 3 lines with NER PERSON
        found_name = False
        doc = nlp("\n".join(lines[:3]))
        for ent in doc.ents:
            if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                name = ent.text
                found_name = True
                break
        
        # Fallback to first line if no NER match
        if not found_name:
            for line in lines[:3]:
                if "@" not in line and "http" not in line and not any(char.isdigit() for char in line):
                    name = line
                    break
    
    # Extract location (heuristic)
    location = "Unknown"
    for line in lines[:6]:
        if "location" in line.lower() or "address" in line.lower() or "based in" in line.lower():
            location = line.replace("Location:", "").replace("Address:", "").strip()
            break
    if location == "Unknown":
        # Search for common Indian city names or Toronto/etc
        cities = ["pune", "noida", "hyderabad", "mumbai", "delhi", "bangalore", "toronto", "vancouver", "san francisco", "new york"]
        for line in lines[:10]:
            for city in cities:
                if city in line.lower():
                    location = city.capitalize()
                    break
            if location != "Unknown":
                break

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "location": location
    }

def extract_skills_from_text(text):
    """Search for skills in the text, map synonyms and resolve them."""
    extracted_skills = []
    text_lower = text.lower()
    
    # Direct match on SKILL_MAP keys
    matched_canonical = set()
    for raw_skill, canonical in SKILL_MAP.items():
        # Match as whole word/phrase
        pattern = r'\b' + re.escape(raw_skill) + r'\b'
        if re.search(pattern, text_lower):
            matched_canonical.add(canonical)
            
    # Format as list of dicts for DB
    for skill_name in matched_canonical:
        # Assign simulated proficiency and duration if not already present
        # In a real parser we might search nearby sentences, for the PoC, we default them.
        extracted_skills.append({
            "name": skill_name,
            "proficiency": "advanced",
            "duration_months": 24, # default
            "endorsements": 5
        })
        
    return extracted_skills

def parse_experience_years(text):
    """Estimate years of experience from resume text."""
    # Pattern to find years of experience statements e.g. "6.9 years of experience", "8+ years"
    exp_pattern = re.compile(r'(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s*(?:of)?\s*(?:experience|exp)', re.IGNORECASE)
    match = exp_pattern.search(text)
    if match:
        return float(match.group(1))
    
    # Or sum durations in career history if available
    # Let's fallback to calculating from date patterns like "2019 - 2024" or "MM/YYYY - Present"
    date_patterns = [
        re.compile(r'\b(19\d{2}|20\d{2})\s*-\s*(19\d{2}|20\d{2}|present|current)\b', re.IGNORECASE),
        re.compile(r'\b(0[1-9]|1[0-2])/(19\d{2}|20\d{2})\s*-\s*(0[1-9]|1[0-2])/(19\d{2}|20\d{2})\b'),
        re.compile(r'\b(0[1-9]|1[0-2])/(19\d{2}|20\d{2})\s*-\s*(present|current)\b', re.IGNORECASE)
    ]
    
    total_months = 0
    for pattern in date_patterns:
        matches = pattern.findall(text)
        for m in matches:
            try:
                # Handle start and end years
                if len(m) == 2:
                    start_year = int(m[0])
                    end_str = m[1].lower()
                    end_year = 2026 if "pres" in end_str or "curr" in end_str else int(m[1])
                    total_months += (end_year - start_year) * 12
                elif len(m) == 4: # MM/YYYY - MM/YYYY
                    start_month, start_year = int(m[0]), int(m[1])
                    end_month, end_year = int(m[2]), int(m[3])
                    total_months += (end_year - start_year) * 12 + (end_month - start_month)
                elif len(m) == 3: # MM/YYYY - Present
                    start_month, start_year = int(m[0]), int(m[1])
                    end_year = 2026
                    end_month = 7
                    total_months += (end_year - start_year) * 12 + (end_month - start_month)
            except:
                continue
                
    if total_months > 0:
        return round(total_months / 12.0, 1)
        
    return 3.0 # Default fallback if nothing found

def parse_resume_pdf(file_path):
    """Main function to parse resume PDF into a structured candidate dictionary."""
    text = extract_pdf_text(file_path)
    contact = parse_contact_details(text)
    skills = extract_skills_from_text(text)
    years_exp = parse_experience_years(text)
    
    # Segment sections to extract career, education, projects, certs
    sections = segment_text_sections(text)
    
    career_history = parse_career_section(sections.get("experience", ""))
    education = parse_education_section(sections.get("education", ""))
    certifications = parse_certs_section(sections.get("certifications", ""))
    
    # Assemble candidate structure
    parsed_cand = {
        "candidate_id": f"CAND_{hash(file_path) % 10000000:07d}",
        "name": contact["name"],
        "email": contact["email"],
        "phone": contact["phone"],
        "linkedin": contact["linkedin"],
        "github": contact["github"],
        "location": contact["location"],
        "raw_text": text,
        "profile": {
            "anonymized_name": contact["name"],
            "headline": f"Parsed Candidate - {years_exp} Years Experience",
            "summary": text[:500] + "...",
            "location": contact["location"],
            "country": "India" if "india" in contact["location"].lower() or any(c in contact["location"].lower() for c in ["pune", "noida", "hyderabad", "mumbai", "delhi", "bangalore"]) else "Unknown",
            "years_of_experience": years_exp,
            "current_title": career_history[0]["title"] if career_history else "Software Engineer",
            "current_company": career_history[0]["company"] if career_history else "Independent",
            "current_company_size": "51-200",
            "current_industry": "Technology"
        },
        "skills": skills,
        "career_history": career_history,
        "education": education,
        "certifications": certifications,
        "languages": [{"language": "English", "proficiency": "professional"}],
        "redrob_signals": {
            "profile_completeness_score": 85.0,
            "signup_date": "2025-01-01",
            "last_active_date": "2026-07-01",
            "open_to_work_flag": True,
            "profile_views_received_30d": 12,
            "applications_submitted_30d": 3,
            "recruiter_response_rate": 0.85,
            "avg_response_time_hours": 4.5,
            "skill_assessment_scores": {},
            "connection_count": 150,
            "endorsements_received": 18,
            "notice_period_days": 30,
            "expected_salary_range_inr_lpa": {"min": 18, "max": 28},
            "preferred_work_mode": "hybrid",
            "willing_to_relocate": True,
            "github_activity_score": 65.0 if contact["github"] else -1,
            "search_appearance_30d": 28,
            "saved_by_recruiters_30d": 4,
            "interview_completion_rate": 1.0,
            "offer_acceptance_rate": 0.90,
            "verified_email": True,
            "verified_phone": True,
            "linkedin_connected": True if contact["linkedin"] else False
        }
    }
    return parsed_cand

def segment_text_sections(text):
    """Segment raw text into sections based on standard headings."""
    headings = {
        "experience": ["experience", "work history", "employment", "career"],
        "education": ["education", "academic", "studies", "qualification"],
        "skills": ["skills", "technologies", "expertise", "specialties"],
        "projects": ["projects", "personal projects", "academic projects"],
        "certifications": ["certifications", "certs", "courses", "credentials"]
    }
    
    sections = {}
    lines = text.split("\n")
    current_section = None
    section_buffer = []
    
    for line in lines:
        clean_line = line.strip().lower().rstrip(":")
        # Check if line matches any section heading
        is_heading = False
        for sec_name, keywords in headings.items():
            if clean_line in keywords or any(clean_line == kw for kw in keywords):
                if current_section:
                    sections[current_section] = "\n".join(section_buffer)
                current_section = sec_name
                section_buffer = []
                is_heading = True
                break
        
        if not is_heading:
            section_buffer.append(line)
            
    if current_section:
        sections[current_section] = "\n".join(section_buffer)
        
    return sections

def parse_career_section(text):
    """Extract job listings from experience section."""
    if not text.strip():
        return []
    # Sample heuristics: look for dates and lines with company / title
    jobs = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    
    # We will split jobs by lines that contain date indicators
    # For now, let's create a generic item from the lines
    if lines:
        # Create a single summary job to make sure the structure is correct
        company = "Unknown Company"
        title = "Software Engineer"
        for line in lines[:4]:
            if "company" in line.lower() or "at " in line.lower():
                company = line.replace("Company:", "").replace("at ", "").strip()
            elif "role" in line.lower() or "title" in line.lower() or "engineer" in line.lower() or "developer" in line.lower():
                title = line.replace("Title:", "").replace("Role:", "").strip()
                
        jobs.append({
            "company": company,
            "title": title,
            "start_date": "2024-01-01",
            "end_date": None,
            "duration_months": 24,
            "is_current": True,
            "industry": "Technology",
            "company_size": "51-200",
            "description": text[:500]
        })
    return jobs

def parse_education_section(text):
    """Extract education listings from education section."""
    if not text.strip():
        return []
    edu = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        institution = "University"
        degree = "B.Tech"
        field = "Computer Science"
        for line in lines[:3]:
            if "college" in line.lower() or "university" in line.lower() or "institute" in line.lower():
                institution = line
            elif "degree" in line.lower() or "b.e." in line.lower() or "b.tech" in line.lower() or "m.s." in line.lower() or "m.tech" in line.lower() or "phd" in line.lower():
                degree = line
                
        edu.append({
            "institution": institution,
            "degree": degree,
            "field_of_study": field,
            "start_year": 2017,
            "end_year": 2021,
            "grade": "First Class",
            "tier": "tier_2"
        })
    return edu

def parse_certs_section(text):
    """Extract certifications listings from certifications section."""
    if not text.strip():
        return []
    certs = []
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        if len(line) > 5:
            certs.append({
                "name": line,
                "issuer": "Coursera / Udemy / AWS",
                "year": 2025
            })
    return certs

def parse_job_description_text(jd_text):
    """Understand and extract job description structured parameters."""
    title = "Senior AI Engineer"
    lines = [l.strip() for l in jd_text.split("\n") if l.strip()]
    if lines:
        for line in lines[:4]:
            if "title:" in line.lower() or "job description:" in line.lower():
                title = line.split(":")[-1].strip()
            elif "role:" in line.lower() or "position:" in line.lower():
                title = line.split(":")[-1].strip()
            elif "engineer" in line.lower() or "developer" in line.lower() or "analyst" in line.lower():
                title = line.strip()
                
    # Experience parsing
    exp_required = 5.0
    exp_match = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)\s*years', jd_text, re.IGNORECASE)
    if exp_match:
        exp_required = float(exp_match.group(1))
    else:
        exp_match2 = re.search(r'(\d+)\+?\s*years', jd_text, re.IGNORECASE)
        if exp_match2:
            exp_required = float(exp_match2.group(1))
        else:
            exp_match3 = re.search(r'(\d+)\s*year', jd_text, re.IGNORECASE)
            if exp_match3:
                exp_required = float(exp_match3.group(1))
            
    # Skills required
    skills = []
    text_lower = jd_text.lower()
    for raw_skill, canonical in SKILL_MAP.items():
        pattern = r'\b' + re.escape(raw_skill) + r'\b'
        if re.search(pattern, text_lower):
            if canonical not in skills:
                skills.append(canonical)
                
    # Location
    location = "Pune/Noida, India"
    loc_match = re.search(r'location:\s*([^\n|]+)', jd_text, re.IGNORECASE)
    if loc_match:
        location = loc_match.group(1).strip()
    else:
        # Check target cities in the text
        cities = ["Bengaluru", "Bangalore", "Noida", "Pune", "Delhi", "Hyderabad", "Mumbai", "Chennai", "Gurgaon"]
        for city in cities:
            if city.lower() in text_lower:
                location = city
                break
        
    # Seniority
    seniority = "Senior"
    if "lead" in text_lower:
        seniority = "Lead"
    elif "principal" in text_lower:
        seniority = "Principal"
    elif "intern" in text_lower:
        seniority = "Intern"
    elif "entry" in text_lower or "junior" in text_lower:
        seniority = "Junior"
    elif "fresh" in text_lower or "associate" in text_lower:
        seniority = "Junior"
        
    # Heuristics for dynamic extraction of responsibilities and qualifications
    responsibilities = []
    requirements = []
    education = "B.E./B.Tech/M.S. in Computer Science or related fields"
    
    current_sec = None
    for line in lines:
        l_low = line.lower()
        if any(h in l_low for h in ["responsibility", "responsibilities", "what you will do", "tasks", "duties", "role"]):
            current_sec = "responsibilities"
            continue
        elif any(h in l_low for h in ["requirement", "requirements", "qualification", "qualifications", "skills", "who you are", "about you"]):
            current_sec = "requirements"
            continue
            
        # Parse bullet items
        if line.startswith(("-", "*", "•", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            clean_item = re.sub(r'^[-\*•\d\.]+\s*', '', line).strip()
            if len(clean_item) > 10:
                if current_sec == "responsibilities":
                    responsibilities.append(clean_item)
                elif current_sec == "requirements":
                    requirements.append(clean_item)
                else:
                    first_word = clean_item.split()[0].lower() if clean_item.split() else ""
                    if any(v in first_word for v in ["build", "design", "develop", "implement", "deploy", "scale", "write", "audit", "lead", "manage", "collaborate", "ensure", "ship", "work"]):
                        responsibilities.append(clean_item)
                    else:
                        requirements.append(clean_item)
                        
    # Fallback if no sections or bullets identified
    if not responsibilities:
        active_verbs = ["build", "design", "develop", "implement", "deploy", "scale", "write", "audit", "lead", "manage", "collaborate", "ensure", "ship", "optimize", "work"]
        for line in lines:
            words = line.split()
            if words:
                first_word = re.sub(r'[^\w]', '', words[0]).lower()
                if first_word in active_verbs and len(line) > 20:
                    responsibilities.append(line)
                    
    if not requirements:
        for line in lines:
            l_low = line.lower()
            if any(k in l_low for k in ["degree", "communication", "collaborate", "experience in", "understanding of", "knowledge of"]):
                requirements.append(line)
                
    # Format and slice
    final_responsibilities = responsibilities[:5]
    if not final_responsibilities:
        final_responsibilities = [
            "Contribute to building and scaling core platform services.",
            "Write clean, readable, and maintainable production code.",
            "Collaborate with engineering teams to deploy ML models.",
            "Analyze and resolve performance issues in systems."
        ]
        
    soft_skills = []
    edu_found = False
    for req in requirements:
        req_low = req.lower()
        if any(e in req_low for e in ["degree", "b.tech", "b.e", "m.s", "m.tech", "phd", "bs/ms", "bachelor", "master"]):
            education = req
            edu_found = True
        else:
            if len(req) < 100 and len(soft_skills) < 4:
                soft_skills.append(req)
                
    if not soft_skills:
        soft_skills = ["Good written and verbal communication.", "Strong problem-solving abilities.", "Ability to work autonomously."]
        
    if not edu_found:
        edu_match = re.search(r'(degree|b\.?tech|b\.?e\.?|m\.?s\.?|m\.?tech|ph\.?d\.?|bachelor|master)\s+[^.\n]+', jd_text, re.IGNORECASE)
        if edu_match:
            education = edu_match.group(0).strip()
            
    return {
        "title": title,
        "experience_required": exp_required,
        "skills": skills,
        "location": location,
        "seniority": seniority,
        "raw_text": jd_text,
        "parsed_data": {
            "industry": "Technology / AI Platforms",
            "responsibilities": final_responsibilities,
            "education": education,
            "soft_skills": soft_skills
        }
    }
