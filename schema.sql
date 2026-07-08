-- SQLite Database Schema for School Management System

-- Table: classes (Class 1 to Class 10)
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- Table: subjects (linked to specific classes)
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    class_id INTEGER NOT NULL,
    FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
    UNIQUE(name, class_id)
);

-- Table: users (Management, Teachers, Students)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'management')),
    class_id INTEGER, -- Only applicable if role is 'student'
    FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE SET NULL
);

-- Table: allocations (teacher assignments to class subjects)
CREATE TABLE IF NOT EXISTS allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
    UNIQUE(teacher_id, subject_id, class_id)
);

-- Table: grades (student grades for subjects, added by allocated teachers)
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    marks INTEGER CHECK(marks >= 0 AND marks <= 100),
    grade TEXT,
    remarks TEXT,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE(student_id, subject_id)
);

-- Table: exams (admin-created exams for a class and subject)
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    class_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    exam_date TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    total_marks INTEGER NOT NULL DEFAULT 100,
    created_by INTEGER NOT NULL,
    FOREIGN KEY(class_id) REFERENCES classes(id) ON DELETE CASCADE,
    FOREIGN KEY(subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
);

-- Table: exam_attendance (student attendance for an exam)
CREATE TABLE IF NOT EXISTS exam_attendance (
    exam_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    attended INTEGER NOT NULL DEFAULT 0,
    attended_at TEXT,
    PRIMARY KEY(exam_id, student_id),
    FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Table: exam_results (teacher-entered marks and pass status)
CREATE TABLE IF NOT EXISTS exam_results (
    exam_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    marks INTEGER NOT NULL,
    grade TEXT,
    remarks TEXT,
    passed INTEGER NOT NULL DEFAULT 0,
    promoted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(exam_id, student_id),
    FOREIGN KEY(exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
);
