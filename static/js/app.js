// Single Page Application (SPA) Logic for School Management System

const API_BASE = window.location.origin.startsWith('file') || window.location.origin.includes('3000')
    ? 'http://localhost:5000'
    : '';

let currentUser = null;
let classesCache = [];

// API Request Wrapper with Header Fallback for Decoupled Setup
async function apiFetch(endpoint, options = {}) {
    options.headers = options.headers || {};
    
    // Fallback credentials headers for file:// and cross-origin usage
    const savedUser = localStorage.getItem('currentUser');
    if (savedUser) {
        const user = JSON.parse(savedUser);
        options.headers['X-User-Id'] = user.id;
        options.headers['X-User-Role'] = user.role;
    }

    options.credentials = 'include'; // for Flask sessions

    if (options.body && typeof options.body === 'object') {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        if (response.status === 401 && endpoint !== '/api/auth/session') {
            // Unauthorized, logout locally
            handleLocalLogout();
        }
        return response;
    } catch (err) {
        console.error("API error:", err);
        showToast("Cannot connect to server. Make sure backend is running.", "error");
        throw err;
    }
}

// Toast Notifications System
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Add icon
    let icon = '';
    if (type === 'success') {
        icon = `<svg viewBox="0 0 24 24" width="20" height="20"><path fill="none" d="M0 0h24v24H0z"/><path d="M12 2c5.52 0 10 4.48 10 10s-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="#10b981"/></svg>`;
    } else {
        icon = `<svg viewBox="0 0 24 24" width="20" height="20"><path fill="none" d="M0 0h24v24H0z"/><path d="M12 2c5.52 0 10 4.48 10 10s-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2zm1 10h-2v5h2v-5zm0-4h-2v2h2V8z" fill="#ef4444"/></svg>`;
    }
    
    toast.innerHTML = `${icon}<span>${message}</span>`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
    setupAuthListeners();
    setupNavigation();
    setupFormListeners();
    
    // Load classes cache
    await loadClasses();
    
    // Check session
    await checkSession();
});

// --- AUTHENTICATION HANDLERS ---

function setupAuthListeners() {
    const showSignupLink = document.getElementById('show-signup');
    const showLoginLink = document.getElementById('show-login');
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');
    const signupRole = document.getElementById('signup-role');
    const signupClassGroup = document.getElementById('signup-class-group');

    // Switch between forms
    showSignupLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginForm.classList.add('hidden');
        signupForm.classList.remove('hidden');
        document.querySelector('.auth-header h2').innerText = "Create Account";
    });

    showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        signupForm.classList.add('hidden');
        loginForm.classList.remove('hidden');
        document.querySelector('.auth-header h2').innerText = "School Portal Login";
    });

    // Handle student class display on register
    signupRole.addEventListener('change', () => {
        if (signupRole.value === 'student') {
            signupClassGroup.classList.remove('hidden');
            document.getElementById('signup-class').setAttribute('required', 'required');
        } else {
            signupClassGroup.classList.add('hidden');
            document.getElementById('signup-class').removeAttribute('required');
        }
    });

    // Login Form Submit
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;

        try {
            const res = await apiFetch('/api/auth/login', {
                method: 'POST',
                body: { email, password }
            });
            const data = await res.json();

            if (res.ok) {
                showToast(data.message, 'success');
                handleLoginSuccess(data.user);
            } else {
                showToast(data.error || 'Login failed.', 'error');
            }
        } catch (err) {
            console.error(err);
        }
    });

    // Signup Form Submit
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('signup-name').value;
        const email = document.getElementById('signup-email').value;
        const password = document.getElementById('signup-password').value;
        const role = document.getElementById('signup-role').value;
        const class_id = document.getElementById('signup-class').value || null;

        try {
            const res = await apiFetch('/api/auth/register', {
                method: 'POST',
                body: { name, email, password, role, class_id }
            });
            const data = await res.json();

            if (res.ok) {
                showToast(data.message, 'success');
                signupForm.reset();
                signupClassGroup.classList.add('hidden');
                // Switch back to login
                signupForm.classList.add('hidden');
                loginForm.classList.remove('hidden');
                document.querySelector('.auth-header h2').innerText = "School Portal Login";
            } else {
                showToast(data.error || 'Registration failed.', 'error');
            }
        } catch (err) {
            console.error(err);
        }
    });

    // Logout Click
    document.getElementById('logout-btn').addEventListener('click', async () => {
        try {
            await apiFetch('/api/auth/logout', { method: 'POST' });
            showToast("Logged out successfully.");
            handleLocalLogout();
        } catch (err) {
            handleLocalLogout();
        }
    });
}

async function checkSession() {
    try {
        const res = await apiFetch('/api/auth/session');
        if (res.ok) {
            const data = await res.json();
            handleLoginSuccess(data.user);
        } else {
            // Check localstorage fallback (useful for file:// open)
            const saved = localStorage.getItem('currentUser');
            if (saved) {
                handleLoginSuccess(JSON.parse(saved));
            } else {
                handleLocalLogout();
            }
        }
    } catch (err) {
        // server connection fail handles locally
        const saved = localStorage.getItem('currentUser');
        if (saved) {
            handleLoginSuccess(JSON.parse(saved));
        } else {
            handleLocalLogout();
        }
    }
}

function handleLoginSuccess(user) {
    currentUser = user;
    localStorage.setItem('currentUser', JSON.stringify(user));
    
    // Hide Auth, Show Dashboard
    document.getElementById('auth-view').classList.add('hidden');
    document.getElementById('dashboard-view').classList.remove('hidden');
    
    // Set Profile Header
    document.getElementById('user-profile-name').innerText = user.name;
    document.getElementById('user-profile-role').innerText = user.role;
    
    // Initials Avatar
    const initials = user.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
    document.getElementById('user-avatar-initials').innerText = initials;

    // Apply role view configurations
    configureRoleNav();
    loadOverview();
    
    // Set Current Date
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    document.getElementById('header-date').innerText = new Date().toLocaleDateString('en-US', options);
}

function handleLocalLogout() {
    currentUser = null;
    localStorage.removeItem('currentUser');
    
    // Show Auth, Hide Dashboard
    document.getElementById('dashboard-view').classList.add('hidden');
    document.getElementById('auth-view').classList.remove('hidden');
    
    // Reset forms
    document.getElementById('login-form').reset();
    document.getElementById('signup-form').reset();
}

function configureRoleNav() {
    // Hide all role specific nav buttons and sections
    document.querySelectorAll('.mgt-only').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.teacher-only').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.student-only').forEach(el => el.classList.add('hidden'));

    if (currentUser.role === 'management') {
        document.querySelectorAll('.mgt-only').forEach(el => el.classList.remove('hidden'));
    } else if (currentUser.role === 'teacher') {
        document.querySelectorAll('.teacher-only').forEach(el => el.classList.remove('hidden'));
    } else if (currentUser.role === 'student') {
        document.querySelectorAll('.student-only').forEach(el => el.classList.remove('hidden'));
    }
}

// --- DYNAMIC DATA POPULATORS ---

async function loadClasses() {
    try {
        const res = await fetch(`${API_BASE}/api/classes`);
        if (res.ok) {
            classesCache = await res.json();
            
            // Populate select lists
            const signupClassSel = document.getElementById('signup-class');
            const mgtClassSel = document.getElementById('mgt-student-class');
            const allocClassSel = document.getElementById('alloc-class');
            
            const optionsHtml = classesCache.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
            
            signupClassSel.innerHTML = `<option value="" disabled selected>Select Class</option>` + optionsHtml;
            mgtClassSel.innerHTML = `<option value="" disabled selected>Select Class</option>` + optionsHtml;
            allocClassSel.innerHTML = `<option value="" disabled selected>Select Class</option>` + optionsHtml;
        }
    } catch (err) {
        console.error("Error loading classes:", err);
    }
}

// Setup Sub-page Navigation Tabs
function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const panes = document.querySelectorAll('.tab-pane');
    const headerTitle = document.getElementById('header-title');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const tabName = item.getAttribute('data-tab');
            
            // Remove active classes
            navItems.forEach(nav => nav.classList.remove('active'));
            panes.forEach(pane => {
                pane.classList.add('hidden');
                pane.classList.remove('active');
            });

            // Set active
            item.classList.add('active');
            const targetPane = document.getElementById(`tab-${tabName}`) || document.getElementById(`tab-view-curriculum`);
            targetPane.classList.remove('hidden');
            targetPane.classList.add('active', 'fade-in');

            // Header titles
            if (tabName === 'overview') headerTitle.innerText = 'Overview Dashboard';
            else if (tabName === 'students-teachers') headerTitle.innerText = 'Roster Directory';
            else if (tabName === 'allocations') headerTitle.innerText = 'Faculty Allocations';
            else if (tabName === 'teacher-grading') headerTitle.innerText = 'Grade Entry Sheet';
            else if (tabName === 'student-grades') headerTitle.innerText = 'Academic Transcript';
            else if (tabName === 'view-curriculum') headerTitle.innerText = 'School Curriculum';

            // Tab-specific loading
            if (tabName === 'overview') loadOverview();
            else if (tabName === 'students-teachers') loadRosterTab();
            else if (tabName === 'allocations') loadAllocationsTab();
            else if (tabName === 'teacher-grading') loadTeacherGradingTab();
            else if (tabName === 'student-grades') loadStudentGradesTab();
            else if (tabName === 'view-curriculum') loadCurriculumTab();
        });
    });

    // Roster Sub Tabs (Teachers vs Students)
    const rosterSubBtns = document.querySelectorAll('[data-roster]');
    rosterSubBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            rosterSubBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const targetTable = btn.getAttribute('data-roster');
            if (targetTable === 'teachers') {
                document.getElementById('teachers-table').classList.remove('hidden');
                document.getElementById('students-table').classList.add('hidden');
            } else {
                document.getElementById('teachers-table').classList.add('hidden');
                document.getElementById('students-table').classList.remove('hidden');
            }
        });
    });
}

// --- OVERVIEW TAB ---
async function loadOverview() {
    const statsGrid = document.getElementById('stats-container');
    const welcomeBox = document.getElementById('role-welcome-box');
    
    welcomeBox.innerHTML = `<p>Loading contextual data...</p>`;
    statsGrid.innerHTML = `<div class="glass-panel stat-card"><p>Loading stats...</p></div>`;

    try {
        if (currentUser.role === 'management') {
            const res = await apiFetch('/api/stats');
            if (res.ok) {
                const stats = await res.json();
                
                statsGrid.innerHTML = `
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M12 2c1.1 0 2 .9 2 2s-.9 2-2 2-2-.9-2-2 .9-2 2-2zm9 7h-6v13h-2v-6h-2v6H9V9H3V7h18v2z" fill="currentColor"/></svg></div>
                        <div class="stat-value">${stats.students}</div>
                        <div class="stat-label">Total Students</div>
                    </div>
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="currentColor"/></svg></div>
                        <div class="stat-value">${stats.teachers}</div>
                        <div class="stat-label">Total Teachers</div>
                    </div>
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10h-4v4h-2v-4H7v-2h4V7h2v4h4v2z" fill="currentColor"/></svg></div>
                        <div class="stat-value">${stats.allocations}</div>
                        <div class="stat-label">Faculty Allocations</div>
                    </div>
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
                        <div class="stat-value">${stats.average_marks}%</div>
                        <div class="stat-label">Average Score</div>
                    </div>
                `;

                welcomeBox.innerHTML = `
                    <h4 style="margin-bottom: 5px; color: white;">Administrative Overview</h4>
                    <p>You have full controls enabled. Register new students and teachers, configure subject structures, and make instructor assignments. Overall, <strong>${stats.grades_recorded}</strong> subjects have been graded.</p>
                `;
            }
        } else if (currentUser.role === 'teacher') {
            const res = await apiFetch('/api/grades');
            if (res.ok) {
                const allocations = await res.json();
                
                // Group by subjects unique to count classes taught
                const uniqueSubjects = new Set(allocations.map(a => `${a.class_name}-${a.subject_name}`));
                const studentCount = new Set(allocations.map(a => a.student_id)).size;

                statsGrid.innerHTML = `
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" fill="currentColor"/></svg></div>
                        <div class="stat-value">${uniqueSubjects.size}</div>
                        <div class="stat-label">Subjects/Classes Taught</div>
                    </div>
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4z" fill="currentColor"/></svg></div>
                        <div class="stat-value">${studentCount}</div>
                        <div class="stat-label">Total Assigned Students</div>
                    </div>
                `;

                welcomeBox.innerHTML = `
                    <h4 style="margin-bottom: 5px; color: white;">Instructor Dashboard</h4>
                    <p>You are allocated to teach <strong>${uniqueSubjects.size}</strong> subjects. Use the <strong>Record Grades</strong> menu to evaluate student marks and upload remarks for report cards.</p>
                `;
            }
        } else if (currentUser.role === 'student') {
            const res = await apiFetch('/api/grades');
            if (res.ok) {
                const grades = await res.json();
                
                const gradedCount = grades.filter(g => g.marks !== null).length;
                const totalCount = grades.length;
                const sum = grades.reduce((acc, g) => acc + (g.marks || 0), 0);
                const avg = gradedCount > 0 ? Math.round(sum / gradedCount) : 0;

                statsGrid.innerHTML = `
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" fill="currentColor"/></svg></div>
                        <div class="stat-value">${totalCount}</div>
                        <div class="stat-label">Total Subjects</div>
                    </div>
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5" fill="none" stroke="currentColor" stroke-width="2"/></svg></div>
                        <div class="stat-value">${gradedCount} / ${totalCount}</div>
                        <div class="stat-label">Subjects Evaluated</div>
                    </div>
                    <div class="glass-panel stat-card">
                        <div class="stat-icon"><svg viewBox="0 0 24 24"><path d="M5 3v18h14V3H5zm12 16H7V5h10v14z" fill="currentColor"/></svg></div>
                        <div class="stat-value">${avg}%</div>
                        <div class="stat-label">Cumulative GPA</div>
                    </div>
                `;

                welcomeBox.innerHTML = `
                    <h4 style="margin-bottom: 5px; color: white;">Student Portal</h4>
                    <p>Welcome! Review your subjects, check your teachers, and inspect graded feedback sheets via the <strong>Report Card</strong> tab in the sidebar.</p>
                `;
            }
        }
    } catch (err) {
        console.error(err);
    }
}

// --- CURRICULUM TAB ---
async function loadCurriculumTab() {
    const container = document.getElementById('curriculum-accordion-container');
    container.innerHTML = `<p>Loading curriculum...</p>`;

    try {
        const res = await fetch(`${API_BASE}/api/subjects`);
        if (res.ok) {
            const allSubjects = await res.json();
            
            // Group by class
            const grouped = {};
            for (let i = 1; i <= 10; i++) {
                grouped[`Class ${i}`] = [];
            }
            
            allSubjects.forEach(s => {
                if (grouped[s.class_name]) {
                    grouped[s.class_name].push(s.name);
                }
            });

            let html = '';
            for (let i = 1; i <= 10; i++) {
                const className = `Class ${i}`;
                
                // If the logged-in user is a student, restrict views to only their assigned class
                if (currentUser && currentUser.role === 'student' && currentUser.class_id) {
                    const studentClass = classesCache.find(c => c.id === parseInt(currentUser.class_id));
                    const studentClassName = studentClass ? studentClass.name : '';
                    if (className !== studentClassName) {
                        continue;
                    }
                }
                
                const subjects = grouped[className];
                
                html += `
                    <div class="glass-panel curriculum-card">
                        <h4>${className}</h4>
                        <div class="curriculum-subjects">
                            ${subjects.map(s => `<span class="subject-badge">${s}</span>`).join('')}
                        </div>
                    </div>
                `;
            }
            container.innerHTML = html;
        }
    } catch (err) {
        console.error(err);
    }
}

// --- ROSTER TAB (Management only) ---
async function loadRosterTab() {
    const teachersBody = document.getElementById('teachers-list-body');
    const studentsBody = document.getElementById('students-list-body');
    
    teachersBody.innerHTML = `<tr><td colspan="3">Loading...</td></tr>`;
    studentsBody.innerHTML = `<tr><td colspan="4">Loading...</td></tr>`;

    // Populate class selector in creation form
    const createRole = document.getElementById('mgt-user-role');
    const createClassGroup = document.getElementById('mgt-student-class-group');
    
    // Add event listener once
    if (!createRole.dataset.listenerSet) {
        createRole.addEventListener('change', () => {
            if (createRole.value === 'student') {
                createClassGroup.classList.remove('hidden');
                document.getElementById('mgt-student-class').setAttribute('required', 'required');
            } else {
                createClassGroup.classList.add('hidden');
                document.getElementById('mgt-student-class').removeAttribute('required');
            }
        });
        createRole.dataset.listenerSet = "true";
    }

    try {
        // 1. Fetch Teachers
        const resT = await apiFetch('/api/teachers');
        if (resT.ok) {
            const teachers = await resT.json();
            teachersBody.innerHTML = teachers.map(t => `
                <tr>
                    <td><strong>${t.name}</strong></td>
                    <td>${t.email}</td>
                    <td><code>TEA-${t.id}</code></td>
                </tr>
            `).join('') || `<tr><td colspan="3">No teachers registered yet.</td></tr>`;
        }

        // 2. Fetch Students
        const resS = await apiFetch('/api/students');
        if (resS.ok) {
            const students = await resS.json();
            studentsBody.innerHTML = students.map(s => `
                <tr>
                    <td><strong>${s.name}</strong></td>
                    <td>${s.email}</td>
                    <td><span class="subject-badge" style="color: white; border-color: rgba(255,255,255,0.15)">${s.class_name || 'N/A'}</span></td>
                    <td><code>STU-${s.id}</code></td>
                </tr>
            `).join('') || `<tr><td colspan="4">No students registered yet.</td></tr>`;
        }
    } catch (err) {
        console.error(err);
    }
}

// --- ALLOCATIONS TAB (Management only) ---
async function loadAllocationsTab() {
    const listBody = document.getElementById('allocations-list-body');
    listBody.innerHTML = `<tr><td colspan="4">Loading...</td></tr>`;

    const teacherSel = document.getElementById('alloc-teacher');
    const classSel = document.getElementById('alloc-class');
    const subjectSel = document.getElementById('alloc-subject');

    // Reset dropdowns
    teacherSel.innerHTML = `<option value="" disabled selected>Select Teacher</option>`;
    subjectSel.innerHTML = `<option value="" disabled selected>Choose Class First</option>`;
    subjectSel.setAttribute('disabled', 'disabled');

    try {
        // Load Teachers dropdown
        const resT = await apiFetch('/api/teachers');
        if (resT.ok) {
            const teachers = await resT.json();
            teacherSel.innerHTML += teachers.map(t => `<option value="${t.id}">${t.name} (${t.email})</option>`).join('');
        }

        // Listen for Class change to load subjects dynamically
        if (!classSel.dataset.listenerSet) {
            classSel.addEventListener('change', async () => {
                const classId = classSel.value;
                subjectSel.innerHTML = `<option value="" disabled selected>Loading subjects...</option>`;
                
                try {
                    const resS = await fetch(`${API_BASE}/api/subjects?class_id=${classId}`);
                    if (resS.ok) {
                        const subjects = await resS.json();
                        subjectSel.innerHTML = `<option value="" disabled selected>Select Subject</option>` +
                            subjects.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
                        subjectSel.removeAttribute('disabled');
                    }
                } catch (e) {
                    console.error(e);
                }
            });
            classSel.dataset.listenerSet = "true";
        }

        // Load Allocations table
        await refreshAllocationsTable();
    } catch (err) {
        console.error(err);
    }
}

async function refreshAllocationsTable() {
    const listBody = document.getElementById('allocations-list-body');
    try {
        const res = await apiFetch('/api/allocations');
        if (res.ok) {
            const allocations = await res.json();
            listBody.innerHTML = allocations.map(a => `
                <tr>
                    <td><strong>${a.teacher_name}</strong><br><small style="color:var(--text-muted)">${a.teacher_email}</small></td>
                    <td><span class="subject-badge" style="color: white; border-color: rgba(255,255,255,0.15)">${a.class_name}</span></td>
                    <td><strong>${a.subject_name}</strong></td>
                    <td>
                        <button class="action-link-danger" onclick="deleteAllocation(${a.id})">Delete</button>
                    </td>
                </tr>
            `).join('') || `<tr><td colspan="4">No allocations registered.</td></tr>`;
        }
    } catch (e) {
        console.error(e);
    }
}

// Expose globally so inline onclick works
window.deleteAllocation = async (id) => {
    if (!confirm("Are you sure you want to delete this allocation?")) return;
    try {
        const res = await apiFetch(`/api/allocations/${id}`, { method: 'DELETE' });
        if (res.ok) {
            showToast("Allocation deleted successfully.");
            await refreshAllocationsTable();
            loadOverview(); // update stats
        } else {
            const err = await res.json();
            showToast(err.error || "Failed to delete.", "error");
        }
    } catch (e) {
        console.error(e);
    }
};

// --- TEACHER GRADING TAB (Teacher only) ---
async function loadTeacherGradingTab() {
    const listBody = document.getElementById('teacher-grades-body');
    listBody.innerHTML = `<tr><td colspan="6">Loading...</td></tr>`;

    const allocSel = document.getElementById('grade-allocation');
    const studentSel = document.getElementById('grade-student');

    allocSel.innerHTML = `<option value="" disabled selected>Select Class / Subject</option>`;
    studentSel.innerHTML = `<option value="" disabled selected>Select Class/Subject First</option>`;
    studentSel.setAttribute('disabled', 'disabled');

    try {
        // Load teacher allocations
        const res = await apiFetch('/api/grades');
        if (res.ok) {
            const sheet = await res.json();
            
            // Render the grades table
            listBody.innerHTML = sheet.map(row => `
                <tr>
                    <td><strong>${row.student_name}</strong></td>
                    <td><span class="subject-badge" style="color: white; border-color: rgba(255,255,255,0.15)">${row.class_name}</span></td>
                    <td><strong>${row.subject_name}</strong></td>
                    <td><span style="font-weight:600">${row.marks !== null ? row.marks : '--'}</span></td>
                    <td><span class="subject-badge" style="color: ${row.grade === 'F' ? 'var(--danger)' : 'var(--secondary)'}; border-color: currentColor">${row.grade || '--'}</span></td>
                    <td><span style="font-style:italic; font-size:12px">${row.remarks || 'No remarks'}</span></td>
                </tr>
            `).join('') || `<tr><td colspan="6">You have no allocations or students assigned.</td></tr>`;

            // Deduplicate allocations list for select drop-down
            const uniqueAllocations = [];
            const seen = new Set();
            
            sheet.forEach(row => {
                const key = `${row.class_name}-${row.subject_name}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    uniqueAllocations.push({
                        class_name: row.class_name,
                        subject_id: row.subject_id,
                        subject_name: row.subject_name
                    });
                }
            });

            allocSel.innerHTML += uniqueAllocations.map(a => `
                <option value="${a.subject_id}" data-classname="${a.class_name}">
                    ${a.class_name} - ${a.subject_name}
                </option>
            `).join('');

            // On allocation change, filter student list
            if (!allocSel.dataset.listenerSet) {
                allocSel.addEventListener('change', () => {
                    const subjectId = parseInt(allocSel.value);
                    const selectedOpt = allocSel.options[allocSel.selectedIndex];
                    const className = selectedOpt.getAttribute('data-classname');
                    
                    // Filter students that match the class
                    const filteredStudents = sheet.filter(row => row.class_name === className && row.subject_id === subjectId);
                    
                    studentSel.innerHTML = `<option value="" disabled selected>Select Student</option>` +
                        filteredStudents.map(s => `<option value="${s.student_id}">${s.student_name}</option>`).join('');
                    studentSel.removeAttribute('disabled');
                });
                allocSel.dataset.listenerSet = "true";
            }
        }
    } catch (err) {
        console.error(err);
    }
}

// --- STUDENT GRADES TAB (Student only) ---
async function loadStudentGradesTab() {
    const body = document.getElementById('student-grades-body');
    body.innerHTML = `<tr><td colspan="5">Loading report card...</td></tr>`;

    try {
        const res = await apiFetch('/api/grades');
        if (res.ok) {
            const grades = await res.json();
            
            body.innerHTML = grades.map(g => `
                <tr>
                    <td><strong>${g.subject_name}</strong></td>
                    <td><span style="font-weight:600">${g.marks !== null ? g.marks : '--'}</span></td>
                    <td><span class="subject-badge" style="color: ${g.grade === 'F' ? 'var(--danger)' : 'var(--secondary)'}; border-color: currentColor">${g.grade || '--'}</span></td>
                    <td><span style="font-style:italic; font-size:12px">${g.remarks || 'No remarks yet'}</span></td>
                    <td><strong>${g.teacher_name || 'Not Assigned'}</strong></td>
                </tr>
            `).join('') || `<tr><td colspan="5">No courses found.</td></tr>`;
        }
    } catch (err) {
        console.error(err);
    }
}

// --- FORMS REGISTRATION SUBMISSIONS ---
function setupFormListeners() {
    // Management Create User Form
    const mgtUserForm = document.getElementById('mgt-create-user-form');
    mgtUserForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('mgt-user-name').value;
        const email = document.getElementById('mgt-user-email').value;
        const password = document.getElementById('mgt-user-password').value;
        const role = document.getElementById('mgt-user-role').value;
        const class_id = document.getElementById('mgt-student-class').value || null;

        try {
            const res = await apiFetch('/api/auth/register', {
                method: 'POST',
                body: { name, email, password, role, class_id }
            });
            const data = await res.json();

            if (res.ok) {
                showToast(`Successfully registered ${role}!`);
                mgtUserForm.reset();
                document.getElementById('mgt-student-class-group').classList.add('hidden');
                await loadRosterTab();
                loadOverview(); // update stats
            } else {
                showToast(data.error || 'Failed to create user.', 'error');
            }
        } catch (err) {
            console.error(err);
        }
    });

    // Management Create Allocation Form
    const mgtAllocForm = document.getElementById('mgt-allocation-form');
    mgtAllocForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const teacher_id = parseInt(document.getElementById('alloc-teacher').value);
        const class_id = parseInt(document.getElementById('alloc-class').value);
        const subject_id = parseInt(document.getElementById('alloc-subject').value);

        try {
            const res = await apiFetch('/api/allocations', {
                method: 'POST',
                body: { teacher_id, class_id, subject_id }
            });
            const data = await res.json();

            if (res.ok) {
                showToast("Teacher allocated successfully!");
                mgtAllocForm.reset();
                document.getElementById('alloc-subject').innerHTML = `<option value="" disabled selected>Choose Class First</option>`;
                document.getElementById('alloc-subject').setAttribute('disabled', 'disabled');
                await refreshAllocationsTable();
                loadOverview(); // update stats
            } else {
                showToast(data.error || 'Failed to create allocation.', 'error');
            }
        } catch (err) {
            console.error(err);
        }
    });

    // Teacher Save Grade Form
    const teacherGradeForm = document.getElementById('teacher-grading-form');
    teacherGradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const student_id = parseInt(document.getElementById('grade-student').value);
        const subject_id = parseInt(document.getElementById('grade-allocation').value);
        const marks = parseInt(document.getElementById('grade-marks').value);
        const remarks = document.getElementById('grade-remarks').value;

        try {
            const res = await apiFetch('/api/grades', {
                method: 'POST',
                body: { student_id, subject_id, marks, remarks }
            });
            const data = await res.json();

            if (res.ok) {
                showToast(`Grade recorded! Scored ${data.grade}.`);
                teacherGradeForm.reset();
                document.getElementById('grade-student').innerHTML = `<option value="" disabled selected>Select Class/Subject First</option>`;
                document.getElementById('grade-student').setAttribute('disabled', 'disabled');
                await loadTeacherGradingTab();
            } else {
                showToast(data.error || 'Failed to record grade.', 'error');
            }
        } catch (err) {
            console.error(err);
        }
    });
}
