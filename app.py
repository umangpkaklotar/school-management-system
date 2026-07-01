import sqlite3
import os
import json
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'school-management-system-super-secret-key-1337')

# Enable CORS for frontend API consumption
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

DB_PATH = 'school.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def save_user_to_json(name, email, role, class_id=None):
    if role == 'student':
        file_path = 'students.json'
    elif role == 'teacher':
        file_path = 'teachers.json'
    else:
        file_path = 'management.json'

    users_list = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                users_list = json.load(f)
        except Exception:
            users_list = []
            
    user_entry = {
        'name': name,
        'email': email,
        'role': role
    }
    if role == 'student':
        user_entry['class_id'] = class_id

    users_list.append(user_entry)
    
    try:
        with open(file_path, 'w') as f:
            json.dump(users_list, f, indent=4)
    except Exception as e:
        print(f"Error writing to JSON ({file_path}): {e}")

def get_current_user():
    """
    Get current logged in user.
    Uses Flask session when running combined.
    Uses X-User-Id & X-User-Role fallback headers for decoupled frontend branch testing (file://).
    """
    if 'user_id' in session:
        return session['user_id'], session['user_role']
    
    # Decoupled / file:// fallback
    user_id = request.headers.get('X-User-Id')
    user_role = request.headers.get('X-User-Role')
    if user_id and user_role:
        try:
            return int(user_id), user_role
        except ValueError:
            pass
    return None, None

@app.route('/')
def serve_index():
    """Serve the single-page application frontend."""
    return app.send_static_file('index.html')

# --- AUTH API ---

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    role = data.get('role', '')
    class_id = data.get('class_id')

    if not name or not email or not password or not role:
        return jsonify({'error': 'All fields are required.'}), 400

    if role not in ['student', 'teacher', 'management']:
        return jsonify({'error': 'Invalid role specified.'}), 400

    if role == 'student' and not class_id:
        return jsonify({'error': 'Class selection is required for students.'}), 400

    hashed_password = generate_password_hash(password)

    conn = get_db()
    cursor = conn.cursor()

    try:
        if role == 'student':
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role, class_id) VALUES (?, ?, ?, ?, ?)",
                (name, email, hashed_password, role, class_id)
            )
        else:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (name, email, hashed_password, role)
            )
        conn.commit()
        # Save registered user to JSON file
        save_user_to_json(name, email, role, class_id)
        return jsonify({'message': 'Registration successful!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email address already exists.'}), 409
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid email or password.'}), 401

    # Store user info in session
    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_role'] = user['role']
    session['user_email'] = user['email']
    session['user_class_id'] = user['class_id']

    return jsonify({
        'message': 'Login successful!',
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'class_id': user['class_id']
        }
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully.'}), 200

@app.route('/api/auth/session', methods=['GET'])
def get_session():
    user_id, user_role = get_current_user()
    if not user_id:
        return jsonify({'error': 'No active session.'}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, class_id FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'User not found.'}), 404

    return jsonify({
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'class_id': user['class_id']
        }
    }), 200


# --- CLASSES & SUBJECTS API ---

@app.route('/api/classes', methods=['GET'])
def get_classes():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM classes ORDER BY id")
    classes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(classes), 200

@app.route('/api/subjects', methods=['GET'])
def get_subjects():
    class_id = request.args.get('class_id')
    conn = get_db()
    cursor = conn.cursor()
    
    if class_id:
        cursor.execute("SELECT * FROM subjects WHERE class_id = ? ORDER BY name", (class_id,))
    else:
        cursor.execute("SELECT s.*, c.name as class_name FROM subjects s JOIN classes c ON s.class_id = c.id ORDER BY s.class_id, s.name")
        
    subjects = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(subjects), 200


# --- USER LISTS API ---

@app.route('/api/teachers', methods=['GET'])
def get_teachers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email FROM users WHERE role = 'teacher' ORDER BY name")
    teachers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(teachers), 200

@app.route('/api/students', methods=['GET'])
def get_students():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.class_id, c.name as class_name 
        FROM users u 
        LEFT JOIN classes c ON u.class_id = c.id 
        WHERE u.role = 'student' 
        ORDER BY c.id, u.name
    """)
    students = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(students), 200


# --- TEACHER ALLOCATIONS API ---

@app.route('/api/allocations', methods=['GET'])
def get_allocations():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.teacher_id, t.name as teacher_name, t.email as teacher_email,
               a.subject_id, s.name as subject_name, a.class_id, c.name as class_name
        FROM allocations a
        JOIN users t ON a.teacher_id = t.id
        JOIN subjects s ON a.subject_id = s.id
        JOIN classes c ON a.class_id = c.id
        ORDER BY c.id, s.name, t.name
    """)
    allocations = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(allocations), 200

@app.route('/api/allocations', methods=['POST'])
def create_allocation():
    user_id, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Admin permission required.'}), 403

    data = request.json or {}
    teacher_id = data.get('teacher_id')
    subject_id = data.get('subject_id')
    class_id = data.get('class_id')

    if not teacher_id or not subject_id or not class_id:
        return jsonify({'error': 'All allocation fields (teacher, subject, class) are required.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO allocations (teacher_id, subject_id, class_id) VALUES (?, ?, ?)",
            (teacher_id, subject_id, class_id)
        )
        conn.commit()
        return jsonify({'message': 'Teacher allocated successfully!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'This teacher is already allocated to this subject in this class.'}), 409
    finally:
        conn.close()

@app.route('/api/allocations/<int:id>', methods=['DELETE'])
def delete_allocation(id):
    user_id, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Admin permission required.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM allocations WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Allocation deleted successfully.'}), 200


# --- GRADES API ---

@app.route('/api/grades', methods=['GET'])
def get_grades():
    user_id, user_role = get_current_user()
    if not user_id:
        return jsonify({'error': 'Unauthorized.'}), 401

    conn = get_db()
    cursor = conn.cursor()

    if user_role == 'student':
        # Retrieve grades for the student
        cursor.execute("""
            SELECT s.name as subject_name, g.marks, g.grade, g.remarks, 
                   t.name as teacher_name
            FROM subjects s
            LEFT JOIN grades g ON s.id = g.subject_id AND g.student_id = ?
            LEFT JOIN allocations a ON s.id = a.subject_id AND s.class_id = a.class_id
            LEFT JOIN users t ON a.teacher_id = t.id
            JOIN users stu ON stu.id = ? AND s.class_id = stu.class_id
            ORDER BY s.name
        """, (user_id, user_id))
        grades = [dict(row) for row in cursor.fetchall()]
        
    elif user_role == 'teacher':
        # Retrieve students and grades for subjects allocated to the teacher
        cursor.execute("""
            SELECT stu.id as student_id, stu.name as student_name, c.name as class_name, 
                   sub.id as subject_id, sub.name as subject_name,
                   g.marks, g.grade, g.remarks
            FROM allocations a
            JOIN classes c ON a.class_id = c.id
            JOIN subjects sub ON a.subject_id = sub.id
            JOIN users stu ON stu.class_id = c.id AND stu.role = 'student'
            LEFT JOIN grades g ON stu.id = g.student_id AND sub.id = g.subject_id
            WHERE a.teacher_id = ?
            ORDER BY c.id, sub.name, stu.name
        """, (user_id,))
        grades = [dict(row) for row in cursor.fetchall()]

    else: # management
        # Retrieve all grades
        cursor.execute("""
            SELECT stu.id as student_id, stu.name as student_name, c.name as class_name, 
                   sub.name as subject_name, g.marks, g.grade, g.remarks, t.name as teacher_name
            FROM users stu
            JOIN classes c ON stu.class_id = c.id
            JOIN subjects sub ON sub.class_id = c.id
            LEFT JOIN grades g ON stu.id = g.student_id AND sub.id = g.subject_id
            LEFT JOIN allocations a ON sub.id = a.subject_id AND c.id = a.class_id
            LEFT JOIN users t ON a.teacher_id = t.id
            WHERE stu.role = 'student'
            ORDER BY c.id, stu.name, sub.name
        """)
        grades = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(grades), 200

@app.route('/api/grades', methods=['POST'])
def save_grade():
    user_id, user_role = get_current_user()
    if user_role != 'teacher':
        return jsonify({'error': 'Unauthorized. Only teachers can record grades.'}), 403

    data = request.json or {}
    student_id = data.get('student_id')
    subject_id = data.get('subject_id')
    marks = data.get('marks')
    remarks = data.get('remarks', '').strip()

    if student_id is None or subject_id is None or marks is None:
        return jsonify({'error': 'Student, subject, and marks are required.'}), 400

    try:
        marks = int(marks)
        if marks < 0 or marks > 100:
            return jsonify({'error': 'Marks must be between 0 and 100.'}), 400
    except ValueError:
        return jsonify({'error': 'Marks must be an integer.'}), 400

    # Determine grade code based on marks
    if marks >= 90: grade = 'A+'
    elif marks >= 80: grade = 'A'
    elif marks >= 70: grade = 'B'
    elif marks >= 60: grade = 'C'
    elif marks >= 50: grade = 'D'
    elif marks >= 40: grade = 'E'
    else: grade = 'F'

    conn = get_db()
    cursor = conn.cursor()

    # Verify if teacher is actually allocated to teach this subject to the student's class
    cursor.execute("""
        SELECT 1 FROM allocations a
        JOIN users stu ON stu.id = ?
        WHERE a.teacher_id = ? AND a.subject_id = ? AND a.class_id = stu.class_id
    """, (student_id, user_id, subject_id))
    
    is_authorized = cursor.fetchone()
    if not is_authorized:
        conn.close()
        return jsonify({'error': 'Unauthorized. You are not allocated to teach this class/subject.'}), 403

    # Insert or update grade
    cursor.execute("""
        INSERT INTO grades (student_id, subject_id, marks, grade, remarks)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(student_id, subject_id) DO UPDATE SET
            marks = excluded.marks,
            grade = excluded.grade,
            remarks = excluded.remarks
    """, (student_id, subject_id, marks, grade, remarks))
    
    conn.commit()
    conn.close()

    return jsonify({'message': 'Grade recorded successfully!', 'grade': grade}), 200


# --- MANAGEMENT STATS API ---

@app.route('/api/stats', methods=['GET'])
def get_stats():
    user_id, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Management access required.'}), 403

    conn = get_db()
    cursor = conn.cursor()

    # Get counts
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
    student_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'teacher'")
    teacher_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM allocations")
    allocation_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM classes")
    class_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM subjects")
    subject_count = cursor.fetchone()[0]

    # Get class sizes
    cursor.execute("""
        SELECT c.name, COUNT(u.id) as student_count
        FROM classes c
        LEFT JOIN users u ON c.id = u.class_id AND u.role = 'student'
        GROUP BY c.id
        ORDER BY c.id
    """)
    class_sizes = [dict(row) for row in cursor.fetchall()]

    # Get overall average marks
    cursor.execute("SELECT AVG(marks) FROM grades")
    avg_marks = cursor.fetchone()[0]
    avg_marks = round(avg_marks, 1) if avg_marks is not None else 0

    # Get count of graded subjects
    cursor.execute("SELECT COUNT(*) FROM grades")
    graded_count = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'students': student_count,
        'teachers': teacher_count,
        'allocations': allocation_count,
        'classes': class_count,
        'subjects': subject_count,
        'class_sizes': class_sizes,
        'average_marks': avg_marks,
        'grades_recorded': graded_count
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
