import sqlite3
import os
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'school-management-system-super-secret-key-1337')
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Enable CORS for frontend API consumption
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

DB_PATH = 'school.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema_migrations(cursor):
    cursor.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in cursor.fetchall()]
    if 'mobile_number' not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN mobile_number TEXT")
    if 'age' not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN age INTEGER")
    if 'profile_image' not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN profile_image TEXT")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_class_history'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE student_class_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                promoted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE
            )
        """)


def initialize_schema():
    conn = get_db()
    cursor = conn.cursor()
    with open('schema.sql', 'r') as f:
        cursor.executescript(f.read())
    ensure_schema_migrations(cursor)
    conn.commit()
    conn.close()


initialize_schema()


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

def save_uploaded_profile_image(file_storage):
    if not file_storage or file_storage.filename == '':
        return None

    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    filename = secure_filename(file_storage.filename)
    if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return None

    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file_storage.save(file_path)
    return f"/uploads/{unique_filename}"


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
    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form
        file_storage = request.files.get('profile_image')
    else:
        data = request.json or {}
        file_storage = None

    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip()
    password = str(data.get('password', ''))
    role = str(data.get('role', '')).strip()
    class_id = data.get('class_id')
    mobile_number = (str(data.get('mobile_number') or '')).strip() or None
    age_value = data.get('age')
    try:
        age = int(age_value) if age_value not in (None, '') else None
    except (TypeError, ValueError):
        age = None
    profile_image = save_uploaded_profile_image(file_storage) if file_storage else None
    if not profile_image and not file_storage:
        profile_image = (str(data.get('profile_image') or '')).strip() or None

    if not name or not email or not password or not role:
        return jsonify({'error': 'All fields are required.'}), 400

    if role not in ['student', 'teacher', 'management']:
        return jsonify({'error': 'Invalid role specified.'}), 400

    if role == 'student' and not class_id:
        return jsonify({'error': 'Class selection is required for students.'}), 400

    if class_id not in [None, '']:
        try:
            class_id = int(class_id)
        except (TypeError, ValueError):
            class_id = None

    hashed_password = generate_password_hash(password)

    conn = get_db()
    cursor = conn.cursor()

    try:
        if role == 'student':
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role, class_id, mobile_number, age, profile_image) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, email, hashed_password, role, class_id, mobile_number, age, profile_image)
            )
            user_id = cursor.lastrowid
            if class_id is not None:
                cursor.execute(
                    "INSERT INTO student_class_history (student_id, class_id) VALUES (?, ?)",
                    (user_id, class_id)
                )
        else:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role, mobile_number, age, profile_image) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, email, hashed_password, role, mobile_number, age, profile_image)
            )
        conn.commit()
        save_user_to_json(name, email, role, class_id)
        return jsonify({'message': 'Registration successful!'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email address already exists.'}), 409
    finally:
        conn.close()


@app.route('/api/users', methods=['POST'])
def create_user():
    user_id, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Management access required.'}), 403

    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form
        file_storage = request.files.get('profile_image')
    else:
        data = request.json or {}
        file_storage = None

    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip()
    password = str(data.get('password', ''))
    role = str(data.get('role', '')).strip()
    class_id = data.get('class_id')
    mobile_number = (str(data.get('mobile_number') or '')).strip() or None
    age_value = data.get('age')
    try:
        age = int(age_value) if age_value not in (None, '') else None
    except (TypeError, ValueError):
        age = None
    profile_image = save_uploaded_profile_image(file_storage) if file_storage else None
    if not profile_image and not file_storage:
        profile_image = (str(data.get('profile_image') or '')).strip() or None

    if not name or not email or not password or not role:
        return jsonify({'error': 'All fields are required.'}), 400

    if role not in ['student', 'teacher', 'management']:
        return jsonify({'error': 'Invalid role specified.'}), 400

    if role == 'student' and not class_id:
        return jsonify({'error': 'Class selection is required for students.'}), 400

    if class_id not in [None, '']:
        try:
            class_id = int(class_id)
        except (TypeError, ValueError):
            class_id = None

    hashed_password = generate_password_hash(password)

    conn = get_db()
    cursor = conn.cursor()
    try:
        if role == 'student':
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role, class_id, mobile_number, age, profile_image) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (name, email, hashed_password, role, class_id, mobile_number, age, profile_image)
            )
            user_id = cursor.lastrowid
            if class_id is not None:
                cursor.execute("INSERT INTO student_class_history (student_id, class_id) VALUES (?, ?)", (user_id, class_id))
        else:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, role, mobile_number, age, profile_image) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, email, hashed_password, role, mobile_number, age, profile_image)
            )
        conn.commit()
        save_user_to_json(name, email, role, class_id)
        return jsonify({'message': 'User created successfully.'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email address already exists.'}), 409
    finally:
        conn.close()


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user_id_session, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Management access required.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.class_id, c.name as class_name,
               u.mobile_number, u.age, u.profile_image
        FROM users u
        LEFT JOIN classes c ON u.class_id = c.id
        WHERE u.id = ?
    """, (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'User not found.'}), 404

    return jsonify({'user': dict(user)}), 200


@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user_id_session, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Management access required.'}), 403

    if request.content_type and 'multipart/form-data' in request.content_type:
        data = request.form
        file_storage = request.files.get('profile_image')
    else:
        data = request.json or {}
        file_storage = None

    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip()
    role = str(data.get('role', '')).strip()
    class_id = data.get('class_id')
    mobile_number = (str(data.get('mobile_number') or '')).strip() or None
    age_value = data.get('age')
    try:
        age = int(age_value) if age_value not in (None, '') else None
    except (TypeError, ValueError):
        age = None
    password = str(data.get('password', ''))
    profile_image = save_uploaded_profile_image(file_storage) if file_storage else None
    if not profile_image and not file_storage:
        profile_image = (str(data.get('profile_image') or '')).strip() or None

    if not name or not email or not role:
        return jsonify({'error': 'All fields are required.'}), 400

    if role not in ['student', 'teacher', 'management']:
        return jsonify({'error': 'Invalid role specified.'}), 400

    if role == 'student' and not class_id:
        return jsonify({'error': 'Class selection is required for students.'}), 400

    if class_id not in [None, '']:
        try:
            class_id = int(class_id)
        except (TypeError, ValueError):
            class_id = None

    conn = get_db()
    cursor = conn.cursor()
    try:
        if role != 'student':
            class_id = None

        update_fields = [
            ('name', name),
            ('email', email),
            ('role', role),
            ('class_id', class_id),
            ('mobile_number', mobile_number),
            ('age', age),
        ]
        if profile_image:
            update_fields.append(('profile_image', profile_image))
        if password:
            update_fields.append(('password_hash', generate_password_hash(password)))

        set_clause = ', '.join([f"{field} = ?" for field, _ in update_fields])
        values = [value for _, value in update_fields] + [user_id]
        cursor.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return jsonify({'message': 'User updated successfully.'}), 200
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email address already exists.'}), 409
    finally:
        conn.close()


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user_id_session, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Management access required.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'User deleted successfully.'}), 200

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, c.name as class_name
        FROM users u
        LEFT JOIN classes c ON u.class_id = c.id
        WHERE u.email = ?
    """, (email,))
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
    session['user_mobile_number'] = user['mobile_number']
    session['user_age'] = user['age']
    session['user_profile_image'] = user['profile_image']

    return jsonify({
        'message': 'Login successful!',
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
            'class_id': user['class_id'],
            'class_name': user['class_name'],
            'mobile_number': user['mobile_number'],
            'age': user['age'],
            'profile_image': user['profile_image']
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
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.class_id, c.name as class_name,
               u.mobile_number, u.age, u.profile_image
        FROM users u
        LEFT JOIN classes c ON u.class_id = c.id
        WHERE u.id = ?
    """, (user_id,))
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
            'class_id': user['class_id'],
            'class_name': user['class_name'],
            'mobile_number': user['mobile_number'],
            'age': user['age'],
            'profile_image': user['profile_image']
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

@app.route('/api/students/<int:student_id>/promote', methods=['POST'])
def promote_student(student_id):
    user_id, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Management access required.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT class_id FROM users WHERE id = ? AND role = 'student'", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({'error': 'Student not found.'}), 404

    try:
        current_class = int(student['class_id'])
    except (TypeError, ValueError):
        conn.close()
        return jsonify({'error': 'Student has no valid class assigned.'}), 400

    if current_class >= 10:
        conn.close()
        return jsonify({'error': 'Student is already in the highest class.'}), 400

    cursor.execute("INSERT INTO student_class_history (student_id, class_id) VALUES (?, ?)", (student_id, current_class))
    cursor.execute("UPDATE users SET class_id = ? WHERE id = ?", (current_class + 1, student_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Student promoted successfully.'}), 200


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


@app.route('/api/profile', methods=['GET'])
def get_profile():
    user_id, user_role = get_current_user()
    if not user_id:
        return jsonify({'error': 'Unauthorized.'}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, class_id, mobile_number, age, profile_image FROM users WHERE id = ?", (user_id,))
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
            'class_id': user['class_id'],
            'mobile_number': user['mobile_number'],
            'age': user['age'],
            'profile_image': user['profile_image']
        }
    }), 200


@app.route('/api/profile', methods=['POST'])
def upload_profile_image():
    user_id, user_role = get_current_user()
    if not user_id:
        return jsonify({'error': 'Unauthorized.'}), 401

    file_storage = request.files.get('profile_image')
    profile_image = save_uploaded_profile_image(file_storage)
    if not profile_image:
        return jsonify({'error': 'Please upload a valid image file.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET profile_image = ? WHERE id = ?", (profile_image, user_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Profile image uploaded successfully.', 'profile_image': profile_image}), 200


@app.route('/api/teacher/history', methods=['GET'])
def get_teacher_history():
    user_id, user_role = get_current_user()
    if not user_id or user_role != 'teacher':
        return jsonify({'error': 'Teacher access required.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.name AS class_name, s.name AS subject_name,
               COUNT(DISTINCT stu.id) AS student_count,
               COUNT(DISTINCT g.student_id) AS graded_count
        FROM allocations a
        JOIN classes c ON a.class_id = c.id
        JOIN subjects s ON a.subject_id = s.id
        LEFT JOIN users stu ON stu.role = 'student' AND stu.class_id = a.class_id
        LEFT JOIN grades g ON g.subject_id = s.id AND g.student_id = stu.id
        WHERE a.teacher_id = ?
        GROUP BY a.class_id, c.name, s.name
        ORDER BY c.name, s.name
    """, (user_id,))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'history': history}), 200


@app.route('/api/student/history', methods=['GET'])
def get_student_history():
    user_id, user_role = get_current_user()
    if not user_id or user_role != 'student':
        return jsonify({'error': 'Student access required.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT class_id FROM users WHERE id = ?", (user_id,))
    student = cursor.fetchone()
    current_class_id = student['class_id'] if student else None

    if current_class_id is None:
        cursor.execute("""
            SELECT c.name as class_name, s.name as subject_name, g.marks, g.grade, g.remarks, t.name as teacher_name
            FROM grades g
            JOIN subjects s ON g.subject_id = s.id
            JOIN classes c ON s.class_id = c.id
            LEFT JOIN allocations a ON s.id = a.subject_id AND s.class_id = a.class_id
            LEFT JOIN users t ON a.teacher_id = t.id
            WHERE g.student_id = ?
            ORDER BY c.id, s.name
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT c.name as class_name, s.name as subject_name, g.marks, g.grade, g.remarks, t.name as teacher_name
            FROM grades g
            JOIN subjects s ON g.subject_id = s.id
            JOIN classes c ON s.class_id = c.id
            LEFT JOIN allocations a ON s.id = a.subject_id AND s.class_id = a.class_id
            LEFT JOIN users t ON a.teacher_id = t.id
            WHERE g.student_id = ? AND s.class_id != ?
            ORDER BY c.id, s.name
        """, (user_id, current_class_id))

    history = [dict(row) for row in cursor.fetchall()]

    cursor.execute("""
        SELECT c.name as class_name, h.promoted_at
        FROM student_class_history h
        JOIN classes c ON h.class_id = c.id
        WHERE h.student_id = ?
        ORDER BY h.promoted_at DESC
    """, (user_id,))
    class_history = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        'history': history,
        'class_history': class_history,
        'current_class_id': current_class_id
    }), 200


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
            JOIN users stu ON stu.role = 'student' AND (
                stu.class_id = c.id OR EXISTS (
                    SELECT 1 FROM grades g_hist
                    WHERE g_hist.student_id = stu.id AND g_hist.subject_id = sub.id
                )
            )
            LEFT JOIN grades g ON stu.id = g.student_id AND sub.id = g.subject_id
            WHERE a.teacher_id = ?
            ORDER BY c.id, sub.name, stu.name
        """, (user_id,))
        grades = [dict(row) for row in cursor.fetchall()]

    else: # management
        # Retrieve all recorded grades and keep them tied to the subject's class for history visibility
        cursor.execute("""
            SELECT stu.id as student_id, stu.name as student_name,
                   c.id as class_id, c.name as class_name,
                   sub.id as subject_id, sub.name as subject_name,
                   g.marks, g.grade, g.remarks, t.name as teacher_name
            FROM grades g
            JOIN users stu ON stu.id = g.student_id AND stu.role = 'student'
            JOIN subjects sub ON sub.id = g.subject_id
            JOIN classes c ON c.id = sub.class_id
            LEFT JOIN allocations a ON sub.id = a.subject_id AND c.id = a.class_id
            LEFT JOIN users t ON a.teacher_id = t.id
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


# --- EXAMS API ---

@app.route('/api/exams', methods=['GET'])
def get_exams():
    user_id, user_role = get_current_user()
    if not user_id:
        return jsonify({'error': 'Unauthorized.'}), 401

    conn = get_db()
    cursor = conn.cursor()

    if user_role == 'student':
        cursor.execute("SELECT class_id FROM users WHERE id = ?", (user_id,))
        student_class = cursor.fetchone()
        if not student_class or not student_class['class_id']:
            conn.close()
            return jsonify([]), 200

        cursor.execute("""
            SELECT e.*, c.name as class_name, s.name as subject_name,
                   creator.name as created_by_name,
                   a.attended, a.attended_at,
                   r.marks, r.grade, r.remarks, r.passed
            FROM exams e
            JOIN classes c ON e.class_id = c.id
            JOIN subjects s ON e.subject_id = s.id
            LEFT JOIN users creator ON e.created_by = creator.id
            LEFT JOIN exam_attendance a ON e.id = a.exam_id AND a.student_id = ?
            LEFT JOIN exam_results r ON e.id = r.exam_id AND r.student_id = ?
            WHERE e.class_id = ?
            ORDER BY e.exam_date, e.title
        """, (user_id, user_id, student_class['class_id']))

    elif user_role == 'teacher':
        cursor.execute("""
            SELECT e.*, c.name as class_name, s.name as subject_name,
                   creator.name as created_by_name
            FROM exams e
            JOIN classes c ON e.class_id = c.id
            JOIN subjects s ON e.subject_id = s.id
            LEFT JOIN users creator ON e.created_by = creator.id
            WHERE EXISTS (
                SELECT 1 FROM allocations a
                WHERE a.class_id = e.class_id
                  AND a.subject_id = e.subject_id
                  AND a.teacher_id = ?
            )
            ORDER BY e.exam_date, e.title
        """, (user_id,))

    else:
        cursor.execute("""
            SELECT e.*, c.name as class_name, s.name as subject_name,
                   creator.name as created_by_name
            FROM exams e
            JOIN classes c ON e.class_id = c.id
            JOIN subjects s ON e.subject_id = s.id
            LEFT JOIN users creator ON e.created_by = creator.id
            ORDER BY e.exam_date, e.title
        """)

    exams = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(exams), 200


@app.route('/api/exams', methods=['POST'])
def create_exam():
    user_id, user_role = get_current_user()
    if user_role != 'management':
        return jsonify({'error': 'Unauthorized. Admin permission required.'}), 403

    data = request.json or {}
    title = data.get('title', '').strip()
    class_id = data.get('class_id')
    subject_id = data.get('subject_id')
    exam_date = data.get('exam_date', '').strip()
    duration_minutes = data.get('duration_minutes')
    total_marks = data.get('total_marks', 100)

    if not title or not class_id or not subject_id or not exam_date:
        return jsonify({'error': 'Title, class, subject, and exam date are required.'}), 400

    try:
        duration_minutes = int(duration_minutes or 60)
        total_marks = int(total_marks or 100)
    except ValueError:
        return jsonify({'error': 'Duration and total marks must be numbers.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO exams (title, class_id, subject_id, exam_date, duration_minutes, total_marks, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, class_id, subject_id, exam_date, duration_minutes, total_marks, user_id))
    conn.commit()
    exam_id = cursor.lastrowid
    conn.close()

    return jsonify({'message': 'Exam created successfully.', 'exam_id': exam_id}), 201


@app.route('/api/exams/<int:exam_id>/attend', methods=['POST'])
def attend_exam(exam_id):
    user_id, user_role = get_current_user()
    if user_role != 'student':
        return jsonify({'error': 'Only students can mark attendance.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO exam_attendance (exam_id, student_id, attended, attended_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(exam_id, student_id) DO UPDATE SET
            attended = 1,
            attended_at = excluded.attended_at
    """, (exam_id, user_id, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Attendance recorded.'}), 200


@app.route('/api/exams/<int:exam_id>/results', methods=['GET'])
def get_exam_results(exam_id):
    user_id, user_role = get_current_user()
    if user_role not in ['teacher', 'management']:
        return jsonify({'error': 'Unauthorized.'}), 403

    conn = get_db()
    cursor = conn.cursor()

    if user_role == 'teacher':
        cursor.execute("""
            SELECT 1 FROM exams e
            JOIN allocations a ON a.class_id = e.class_id AND a.subject_id = e.subject_id
            WHERE e.id = ? AND a.teacher_id = ?
        """, (exam_id, user_id))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Unauthorized for this exam.'}), 403

    cursor.execute("""
        SELECT e.class_id, e.subject_id, e.total_marks, e.id as exam_id
        FROM exams e
        WHERE e.id = ?
    """, (exam_id,))
    exam = cursor.fetchone()
    if not exam:
        conn.close()
        return jsonify({'error': 'Exam not found.'}), 404

    cursor.execute("""
        SELECT u.id as student_id, u.name as student_name,
               a.attended, a.attended_at,
               r.marks, r.grade, r.remarks, r.passed
        FROM users u
        LEFT JOIN exam_attendance a ON a.exam_id = ? AND a.student_id = u.id
        LEFT JOIN exam_results r ON r.exam_id = ? AND r.student_id = u.id
        WHERE u.role = 'student' AND u.class_id = ?
        ORDER BY u.name
    """, (exam_id, exam_id, exam['class_id']))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'exam_id': exam_id, 'results': results}), 200


@app.route('/api/exams/<int:exam_id>/results', methods=['POST'])
def save_exam_result(exam_id):
    user_id, user_role = get_current_user()
    if user_role != 'teacher':
        return jsonify({'error': 'Only teachers can record exam marks.'}), 403

    data = request.json or {}
    student_id = data.get('student_id')
    marks = data.get('marks')
    remarks = data.get('remarks', '').strip()

    if student_id is None or marks is None:
        return jsonify({'error': 'Student and marks are required.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.class_id, e.subject_id, e.total_marks, e.id as exam_id
        FROM exams e
        WHERE e.id = ?
    """, (exam_id,))
    exam = cursor.fetchone()
    if not exam:
        conn.close()
        return jsonify({'error': 'Exam not found.'}), 404

    cursor.execute("""
        SELECT 1 FROM allocations a
        WHERE a.class_id = ? AND a.subject_id = ? AND a.teacher_id = ?
    """, (exam['class_id'], exam['subject_id'], user_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Unauthorized for this exam.'}), 403

    try:
        marks = int(marks)
        if marks < 0 or marks > int(exam['total_marks']):
            return jsonify({'error': f'Marks must be between 0 and {exam["total_marks"]}.'}), 400
    except ValueError:
        return jsonify({'error': 'Marks must be an integer.'}), 400

    if marks >= 90:
        grade = 'A+'
    elif marks >= 80:
        grade = 'A'
    elif marks >= 70:
        grade = 'B'
    elif marks >= 60:
        grade = 'C'
    elif marks >= 50:
        grade = 'D'
    elif marks >= 40:
        grade = 'E'
    else:
        grade = 'F'

    passed = 1 if marks >= 40 else 0
    promoted = 0

    cursor.execute("""
        INSERT INTO exam_results (exam_id, student_id, marks, grade, remarks, passed, promoted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(exam_id, student_id) DO UPDATE SET
            marks = excluded.marks,
            grade = excluded.grade,
            remarks = excluded.remarks,
            passed = excluded.passed,
            promoted = excluded.promoted
    """, (exam_id, student_id, marks, grade, remarks, passed, promoted))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Exam result saved.', 'grade': grade, 'passed': bool(passed), 'promoted': bool(promoted)}), 200


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
