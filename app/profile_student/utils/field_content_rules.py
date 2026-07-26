from typing import Any, Dict

FIELD_CONTENT_RULES: Dict[str, Dict[str, Any]] = {
    "personal_info.full_name": {
        "rules": [
            {"type": "not_empty"},
            {"type": "not_numeric"},
            {"type": "min_words", "count": 2, "message": "Must include both first and last name"},
            {"type": "regex", "pattern": r"^[A-Za-z\s'-]+$", "message": "Must contain only letters, spaces, hyphens and apostrophes"},
        ],
        "example_valid": "Jesus Gonzalez",
        "example_invalid": "Jesus",
    },
    "personal_info.date_of_birth": {
        "rules": [
            {"type": "not_empty"},
            {"type": "date", "formats": ["%Y-%m-%d", "%d/%m/%Y"], "min_age": 16, "max_age": 60},
        ],
        "example_valid": "2000-03-15",
        "example_invalid": "02-30-2000",
    },
    "personal_info.email": {
        "rules": [
            {"type": "not_empty"},
            {"type": "regex", "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", "message": "Must be a valid email address"},
        ],
        "example_valid": "estudiante@ejemplo.com",
        "example_invalid": "estudiante@",
    },
    "personal_info.phone": {
        "rules": [
            {"type": "not_empty"},
            {"type": "regex", "pattern": r"^[\d\s\+\-()]{7,20}$", "message": "Must contain only digits, spaces, +, -, and parentheses"},
        ],
        "example_valid": "+58 412 123 4567",
        "example_invalid": "abcdefg",
    },
    "personal_info.location.country": {
        "rules": [
            {"type": "not_empty"},
        ],
        "example_valid": "Venezuela",
        "example_invalid": "",
    },
    "personal_info.location.city": {
        "rules": [
            {"type": "not_empty"},
        ],
        "example_valid": "Caracas",
        "example_invalid": "",
    },
    "education.highest_degree.type": {
        "rules": [
            {"type": "not_empty"},
            {"type": "enum", "values": ["high_school", "associate", "bachelor", "master", "phd", "bootcamp", "self_taught"]},
        ],
        "example_valid": "bachelor",
        "example_invalid": "universidad",
    },
    "education.field_of_study": {
        "rules": [
            {"type": "not_empty"},
            {"type": "not_numeric"},
        ],
        "example_valid": "Computer Science",
        "example_invalid": "12345",
    },
    "education.university_or_source": {
        "rules": [
            {"type": "not_empty"},
        ],
        "example_valid": "Universidad Central de Venezuela",
        "example_invalid": "",
    },
    "education.graduation_year": {
        "rules": [
            {"type": "not_empty"},
            {"type": "number_range", "min": 1980, "max": 2050},
        ],
        "example_valid": "2023",
        "example_invalid": "1800",
    },
    "education.if_bachelor_or_higher.gpa": {
        "rules": [
            {"type": "number_range", "min": 0.0, "max": 5.0},
        ],
        "example_valid": "3.5",
        "example_invalid": "6.0",
    },
    "experience.years_of_experience": {
        "rules": [
            {"type": "not_empty"},
            {"type": "number_range", "min": 0, "max": 50},
        ],
        "example_valid": "3",
        "example_invalid": "-1",
    },
    "experience.current_role": {
        "rules": [
            {"type": "not_empty"},
        ],
        "example_valid": "Junior Developer",
        "example_invalid": "",
    },
    "experience.current_company": {
        "rules": [
            {"type": "not_empty"},
        ],
        "example_valid": "Tech Corp",
        "example_invalid": "",
    },
    "experience.work_history_summary": {
        "rules": [
            {"type": "min_words", "count": 10},
        ],
        "example_valid": "I worked as a developer for 2 years building web apps with React and Node.js.",
        "example_invalid": "Short.",
    },
    "experience.if_experienced.primary_technologies": {
        "rules": [
            {"type": "min_words", "count": 2},
        ],
        "example_valid": "Python Django PostgreSQL",
        "example_invalid": "N/A",
    },
    "experience.if_experienced.team_size_led": {
        "rules": [
            {"type": "number_range", "min": 0, "max": 500},
        ],
        "example_valid": "5",
        "example_invalid": "1000",
    },
    "skills.programming_languages": {
        "rules": [
            {"type": "min_words", "count": 1},
        ],
        "example_valid": "Python, JavaScript",
        "example_invalid": "",
    },
    "skills.soft_skills": {
        "rules": [
            {"type": "min_words", "count": 2},
        ],
        "example_valid": "Communication, teamwork",
        "example_invalid": "None",
    },
    "skills.languages_spoken": {
        "rules": [
            {"type": "not_empty"},
        ],
        "example_valid": "Spanish, English",
        "example_invalid": "",
    },
    "interests_projects.preferred_technologies": {
        "rules": [
            {"type": "min_words", "count": 1},
        ],
        "example_valid": "AI, Cloud computing",
        "example_invalid": "",
    },
    "interests_projects.hobbies": {
        "rules": [
            {"type": "min_words", "count": 2},
        ],
        "example_valid": "Coding side projects, gaming",
        "example_invalid": "None",
    },
    "interests_projects.career_goals": {
        "rules": [
            {"type": "min_words", "count": 5},
        ],
        "example_valid": "I want to become a machine learning engineer working on NLP.",
        "example_invalid": "Get a job.",
    },
    "interests_projects.notable_projects": {
        "rules": [
            {"type": "min_words", "count": 5},
        ],
        "example_valid": "Built an e-commerce platform with React and Node.js.",
        "example_invalid": "Nothing.",
    },
    "interests_projects.github_or_portfolio": {
        "rules": [
            {"type": "regex", "pattern": r"^(https?://)?[\w\-]+(\.[\w\-]+)+[/\w\-\.]*$", "message": "Must be a valid URL"},
        ],
        "example_valid": "https://github.com/student",
        "example_invalid": "not-a-url",
    },
}
