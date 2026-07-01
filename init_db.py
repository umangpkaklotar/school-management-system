import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = 'school.db'
SCHEMA_PATH = 'schema.sql'

def init_database():
    print("Initializing database...")
    
    # Connect and execute schema
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    with open(SCHEMA_PATH, 'r') as f:
        schema_sql = f.read()
    
    cursor.executescript(schema_sql)
    conn.commit()
    print("Database tables created.")

    # Populate Classes (1 to 10)
    classes_data = [f"Class {i}" for i in range(1, 11)]
    for class_name in classes_data:
        cursor.execute("INSERT OR IGNORE INTO classes (name) VALUES (?)", (class_name,))
    conn.commit()
    print("Classes 1 to 10 inserted.")

    # Populate Class-wise Subjects
    # Defining distinct subject sets for different classes
    class_subjects = {
        "Class 1": ["English", "Mathematics", "Art & Craft", "General Knowledge"],
        "Class 2": ["English", "Mathematics", "Art & Craft", "General Knowledge", "Environmental Studies (EVS)"],
        "Class 3": ["English", "Mathematics", "Art & Craft", "General Knowledge", "Environmental Studies (EVS)", "Computer Basics"],
        "Class 4": ["English", "Mathematics", "Science", "Social Studies", "Art", "Computer Basics"],
        "Class 5": ["English", "Mathematics", "Science", "Social Studies", "Art", "Computer Basics", "Hindi"],
        "Class 6": ["English", "Mathematics", "Physics", "Chemistry", "Biology", "History & Civics", "Geography", "Computer Science"],
        "Class 7": ["English", "Mathematics", "Physics", "Chemistry", "Biology", "History & Civics", "Geography", "Computer Science", "Second Language (Hindi/French)"],
        "Class 8": ["English", "Mathematics", "Physics", "Chemistry", "Biology", "History & Civics", "Geography", "Computer Science", "Second Language (Hindi/French)"],
        "Class 9": ["English", "Mathematics", "Physics", "Chemistry", "Biology", "History", "Civics & Economics", "Geography", "Computer Applications"],
        "Class 10": ["English", "Mathematics", "Physics", "Chemistry", "Biology", "History", "Civics & Economics", "Geography", "Computer Applications", "Environmental Science"]
    }

    for class_name, subjects in class_subjects.items():
        # Get class ID
        cursor.execute("SELECT id FROM classes WHERE name = ?", (class_name,))
        class_id = cursor.fetchone()[0]
        
        # Insert subjects for this class
        for subject_name in subjects:
            cursor.execute(
                "INSERT OR IGNORE INTO subjects (name, class_id) VALUES (?, ?)", 
                (subject_name, class_id)
            )
            
    conn.commit()
    print("Class-wise subjects inserted.")

    # Create Default Management User
    admin_email = "admin@school.com"
    admin_password = "admin123"
    admin_name = "System Administrator"
    admin_role = "management"
    
    # Hash password using Werkzeug (standard Flask security)
    hashed_password = generate_password_hash(admin_password)
    
    # Check if admin already exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (admin_email,))
    existing_admin = cursor.fetchone()
    
    if not existing_admin:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (admin_name, admin_email, hashed_password, admin_role)
        )
        conn.commit()
        print(f"Default Admin created: {admin_email} / {admin_password}")
    else:
        print("Default Admin already exists.")
        
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    init_database()
