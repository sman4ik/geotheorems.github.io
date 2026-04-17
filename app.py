"""
Geometry Theorems Educational Platform
Simple Flask application for school presentation
"""

import os
import json
import sqlite3
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
from werkzeug.utils import secure_filename
from theorems_data import THEOREMS, THEOREM_LIST

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['DATABASE'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'geometry.db')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'img')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
SUBMISSION_EXTENSIONS = IMAGE_EXTENSIONS | {'pdf', 'txt', 'doc', 'docx'}
PROGRESS_COOKIE_NAME = 'geometry_progress_id'
PROGRESS_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 5  # 5 years


@app.context_processor
def inject_theorems():
    """Make theorem list available in all templates"""
    return {'theorem_list': THEOREM_LIST}


@app.before_request
def init_database():
    """Initialize database on first request"""
    if not hasattr(app, '_db_initialized'):
        init_db()
        migrate_schema()
        app._db_initialized = True


def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.template_filter('from_json')
def from_json_filter(value):
    """Parse JSON string to Python object (template helper)"""
    return parse_json_field(value)


def dict_from_row(row):
    """Convert sqlite3.Row to dictionary"""
    return dict(row) if row else None


def parse_json_field(value, default=None):
    """Parse JSON string, return default on failure"""
    if default is None:
        default = []
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed"""
    if allowed_extensions is None:
        allowed_extensions = IMAGE_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_uploaded_file(file, custom_filename=None, allowed_extensions=None, target_folder=None):
    """Save uploaded file and return the filename"""
    if not file or not file.filename:
        return None

    if custom_filename:
        filename = secure_filename(custom_filename)
    else:
        filename = secure_filename(file.filename)

    if not filename or not allowed_file(filename, allowed_extensions):
        return None

    upload_folder = target_folder or app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    return filename


def init_db():
    """Initialize database with tables"""
    db_path = app.config['DATABASE']
    db_dir = os.path.dirname(db_path)

    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS task (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                theorem_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                hints TEXT,
                solution_type TEXT DEFAULT 'solution',
                solution TEXT NOT NULL,
                image_path TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_task (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                is_solved BOOLEAN DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                last_attempt TIMESTAMP,
                needs_review BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES task(id) ON DELETE CASCADE,
                UNIQUE(session_id, task_id)
            );

            CREATE INDEX IF NOT EXISTS idx_user_task_session ON user_task(session_id);
            CREATE INDEX IF NOT EXISTS idx_user_task_task ON user_task(task_id);
        ''')
        db.commit()
        migrate_schema()


def get_table_columns(db, table_name):
    rows = db.execute(f'PRAGMA table_info({table_name})').fetchall()
    return {row['name'] for row in rows}


def ensure_column(db, table_name, column_name, definition):
    if column_name not in get_table_columns(db, table_name):
        db.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}')


def migrate_schema():
    db = get_db()
    ensure_column(db, 'user_task', 'submission_file_name', 'TEXT')
    ensure_column(db, 'user_task', 'submission_file_path', 'TEXT')
    ensure_column(db, 'user_task', 'submitted_at', 'TIMESTAMP')
    db.commit()


def get_or_create_session():
    """Get or create a persistent ID for tracking user progress."""
    progress_id = request.cookies.get(PROGRESS_COOKIE_NAME)
    if progress_id:
        return progress_id

    if not hasattr(g, 'progress_id'):
        g.progress_id = f"user_{secrets.token_hex(8)}"
    return g.progress_id


@app.after_request
def persist_progress_cookie(response):
    """Store the progress ID in a long-lived cookie so solved tasks survive reloads."""
    progress_id = getattr(g, 'progress_id', None)
    if progress_id and request.cookies.get(PROGRESS_COOKIE_NAME) != progress_id:
        response.set_cookie(
            PROGRESS_COOKIE_NAME,
            progress_id,
            max_age=PROGRESS_COOKIE_MAX_AGE,
            httponly=True,
            samesite='Lax',
            secure=request.is_secure,
        )
    return response


def ensure_user_task(session_id, task_id):
    """Ensure user_task record exists, create if needed"""
    db = get_db()
    db.execute('INSERT OR IGNORE INTO user_task (session_id, task_id) VALUES (?, ?)', (session_id, task_id))
    db.commit()
    return db.execute('SELECT * FROM user_task WHERE session_id = ? AND task_id = ?', (session_id, task_id)).fetchone()


def update_task_progress(session_id, task_id, action):
    """Update task progress (solved / review / attempt)"""
    db = get_db()
    ensure_user_task(session_id, task_id)
    
    if action == 'solved':
        db.execute(
            'UPDATE user_task SET is_solved = 1, needs_review = 0, attempts = attempts + 1, last_attempt = CURRENT_TIMESTAMP WHERE session_id = ? AND task_id = ?',
            (session_id, task_id)
        )
    elif action == 'review':
        db.execute(
            'UPDATE user_task SET needs_review = 1, attempts = attempts + 1, last_attempt = CURRENT_TIMESTAMP WHERE session_id = ? AND task_id = ?',
            (session_id, task_id)
        )
    else:
        db.execute(
            'UPDATE user_task SET attempts = attempts + 1, last_attempt = CURRENT_TIMESTAMP WHERE session_id = ? AND task_id = ?',
            (session_id, task_id)
        )
    db.commit()



def parse_form_hints(form):
    """Extract hints from form data"""
    return parse_json_field(form.get('hints', '[]'))


# ====== ROUTES ======

@app.route('/')
def index():
    """Homepage"""
    return render_template('index.html')


@app.route('/theorems/<theorem_type>')
def theorem_page(theorem_type):
    """Theorem detail page"""
    if theorem_type not in THEOREMS:
        return redirect(url_for('index'))

    theorem = THEOREMS[theorem_type]
    return render_template('theorems/theorem_detail.html', theorem=theorem)


@app.route('/tasks')
def tasks_list():
    """Task catalog page"""
    theorem_type = request.args.get('theorem')
    return render_template('tasks/tasks_list.html', theorem_type=theorem_type)


@app.route('/api/tasks')
def api_tasks():
    """API endpoint — returns all tasks with user progress"""
    try:
        db = get_db()
        tasks = [dict_from_row(r) for r in db.execute(
            'SELECT * FROM task WHERE is_active = 1 ORDER BY created_at DESC'
        ).fetchall()]

        # Add user progress to each task
        session_id = get_or_create_session()
        user_tasks = db.execute(
            'SELECT task_id, is_solved, needs_review, attempts FROM user_task WHERE session_id = ?',
            (session_id,)
        ).fetchall()
        user_task_map = {row['task_id']: dict_from_row(row) for row in user_tasks}

        # Merge progress into tasks
        for task in tasks:
            ut = user_task_map.get(task['id'])
            task['is_solved'] = bool(ut['is_solved']) if ut else False
            task['needs_review'] = bool(ut['needs_review']) if ut else False
            task['attempts'] = ut['attempts'] if ut else 0

        return jsonify({'tasks': tasks})
    except Exception as e:
        return jsonify({'error': 'Ошибка загрузки задач', 'message': str(e)}), 500


@app.route('/task/<int:task_id>')
def task_detail(task_id):
    """Individual task page"""
    db = get_db()
    cursor = db.cursor()

    cursor.execute('SELECT * FROM task WHERE id = ?', (task_id,))
    task = dict_from_row(cursor.fetchone())

    if not task:
        return redirect(url_for('tasks_list'))

    session_id = get_or_create_session()
    user_task = db.execute(
        'SELECT is_solved, needs_review, attempts, submission_file_name, submission_file_path, submitted_at FROM user_task WHERE session_id = ? AND task_id = ?',
        (session_id, task_id)
    ).fetchone()

    progress = {
        'is_solved': bool(user_task['is_solved']) if user_task else False,
        'needs_review': bool(user_task['needs_review']) if user_task else False,
        'attempts': user_task['attempts'] if user_task else 0,
    }

    return render_template(
        'tasks/task_detail.html',
        task=task,
        progress=progress,
        user_task=dict_from_row(user_task),
        can_view_solution=progress['is_solved'],
    )



# ====== TASK PROGRESS ======

@app.route('/task/<int:task_id>/progress', methods=['GET'])
def get_task_progress(task_id):
    """Get user's progress on a task"""
    try:
        session_id = get_or_create_session()
        db = get_db()
        user_task = db.execute(
            'SELECT is_solved, needs_review, attempts FROM user_task WHERE session_id = ? AND task_id = ?',
            (session_id, task_id)
        ).fetchone()

        return jsonify({
            'is_solved': bool(user_task['is_solved']) if user_task else False,
            'needs_review': bool(user_task['needs_review']) if user_task else False,
            'attempts': user_task['attempts'] if user_task else 0
        })
    except Exception as e:
        app.logger.error(f'Error getting progress for task {task_id}: {str(e)}')
        return jsonify({'error': 'Произошла ошибка', 'message': 'Ошибка при получении прогресса'}), 500


@app.route('/task/<int:task_id>/mark-progress', methods=['POST'])
def mark_task_progress(task_id):
    """Mark task progress (solved or review)"""
    try:
        db = get_db()
        task = dict_from_row(db.execute('SELECT * FROM task WHERE id = ?', (task_id,)).fetchone())
        if not task:
            return jsonify({'error': 'Task not found'}), 404

        session_id = get_or_create_session()
        action = request.form.get('action', 'attempt')

        if action not in ('solved', 'review', 'attempt'):
            return jsonify({'error': 'Invalid action'}), 400

        update_task_progress(session_id, task_id, action)

        return jsonify({'success': True, 'message': 'Прогресс обновлён'})
    except Exception as e:
        app.logger.error(f'Error marking progress for task {task_id}: {str(e)}')
        return jsonify({'error': 'Произошла ошибка', 'message': 'Ошибка при сохранении прогресса'}), 500


@app.route('/task/<int:task_id>/submit-file', methods=['POST'])
def submit_task_file(task_id):
    """Submit a file as the task answer and unlock the solution."""
    try:
        db = get_db()
        task = dict_from_row(db.execute('SELECT * FROM task WHERE id = ?', (task_id,)).fetchone())
        if not task:
            return jsonify({'error': 'Task not found', 'message': 'Задача не найдена'}), 404

        uploaded_file = request.files.get('answer-file')
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({'error': 'No file provided', 'message': 'Прикрепите файл перед отправкой'}), 400

        session_id = get_or_create_session()
        ensure_user_task(session_id, task_id)

        file_ext = uploaded_file.filename.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.filename else ''
        if not allowed_file(uploaded_file.filename, SUBMISSION_EXTENSIONS):
            return jsonify({'error': 'Invalid file type', 'message': 'Этот тип файла не поддерживается'}), 400

        storage_name = f"task_{task_id}_{session_id}_{secrets.token_hex(4)}.{file_ext}"
        upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'task_answers')
        saved_name = save_uploaded_file(
            uploaded_file,
            custom_filename=storage_name,
            allowed_extensions=SUBMISSION_EXTENSIONS,
            target_folder=upload_dir,
        )
        if not saved_name:
            return jsonify({'error': 'Upload failed', 'message': 'Не удалось сохранить файл'}), 500

        saved_path = f"uploads/task_answers/{saved_name}"
        db.execute(
            '''
            UPDATE user_task
            SET is_solved = 1,
                needs_review = 0,
                attempts = attempts + 1,
                last_attempt = CURRENT_TIMESTAMP,
                submission_file_name = ?,
                submission_file_path = ?,
                submitted_at = CURRENT_TIMESTAMP
            WHERE session_id = ? AND task_id = ?
            ''',
            (uploaded_file.filename, saved_path, session_id, task_id)
        )
        db.commit()

        return jsonify({
            'success': True,
            'message': 'Файл отправлен',
            'solution': task['solution'],
            'solution_type': task.get('solution_type', 'solution'),
            'solution_label': 'Доказательство' if task.get('solution_type') == 'proof' else 'Решение',
            'file_name': uploaded_file.filename,
            'file_url': url_for('static', filename=saved_path),
            'submission_file_url': url_for('static', filename=saved_path),
            'submission_file_path': saved_path,
        })
    except Exception as e:
        app.logger.error(f'Error submitting file for task {task_id}: {str(e)}')
        return jsonify({'error': 'Произошла ошибка', 'message': 'Ошибка при отправке файла'}), 500


# ====== ADMIN ROUTES ======

@app.route('/add-task')
def add_task():
    """Добавление новых задач"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM task ORDER BY created_at DESC')
    tasks = [dict_from_row(row) for row in cursor.fetchall()]
    return render_template('admin/tasks.html', tasks=tasks)


@app.route('/add-task/new', methods=['GET', 'POST'])
def add_task_new():
    """Add new task"""
    if request.method == 'POST':
        # Validate required fields
        required_fields = ['title', 'description', 'theorem_type', 'difficulty', 'solution']
        missing = [f for f in required_fields if not request.form.get(f)]
        if missing:
            return render_template('admin/task_form.html', task=None, error=f'Отсутствуют обязательные поля: {", ".join(missing)}')

        # Validate theorem_type
        if request.form.get('theorem_type') not in THEOREMS:
            return render_template('admin/task_form.html', task=None, error='Неверный тип теоремы')

        # Validate difficulty
        if request.form.get('difficulty') not in ('easy', 'medium', 'hard'):
            return render_template('admin/task_form.html', task=None, error='Неверный уровень сложности')

        hints = parse_form_hints(request.form)
        
        # Handle image upload
        image_path = request.form.get('image_path', '')
        if 'image-file' in request.files:
            uploaded_file = request.files['image-file']
            if uploaded_file and uploaded_file.filename:
                saved_filename = save_uploaded_file(uploaded_file, image_path)
                if saved_filename:
                    image_path = saved_filename

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            'INSERT INTO task (title, description, theorem_type, difficulty, hints, solution_type, solution, image_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (request.form.get('title'), request.form.get('description'), request.form.get('theorem_type'),
             request.form.get('difficulty'), json.dumps(hints), request.form.get('solution_type', 'solution'),
             request.form.get('solution'), image_path)
        )
        db.commit()
        return redirect(url_for('add_task'))

    return render_template('admin/task_form.html', task=None)


@app.route('/add-task/<int:task_id>/edit', methods=['GET', 'POST'])
def add_task_edit(task_id):
    """Edit task"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM task WHERE id = ?', (task_id,))
    task = dict_from_row(cursor.fetchone())

    if not task:
        return redirect(url_for('add_task'))

    if request.method == 'POST':
        # Validate required fields
        required_fields = ['title', 'description', 'theorem_type', 'difficulty', 'solution']
        missing = [f for f in required_fields if not request.form.get(f)]
        if missing:
            return render_template('admin/task_form.html', task=task, error=f'Отсутствуют обязательные поля: {", ".join(missing)}')

        # Validate theorem_type
        if request.form.get('theorem_type') not in THEOREMS:
            return render_template('admin/task_form.html', task=task, error='Неверный тип теоремы')

        # Validate difficulty
        if request.form.get('difficulty') not in ('easy', 'medium', 'hard'):
            return render_template('admin/task_form.html', task=task, error='Неверный уровень сложности')

        hints = parse_form_hints(request.form)
        
        # Handle image upload (keep existing if no new upload)
        image_path = task.get('image_path', '')
        if 'image-file' in request.files:
            uploaded_file = request.files['image-file']
            if uploaded_file and uploaded_file.filename:
                new_image_path = request.form.get('image_path', '')
                saved_filename = save_uploaded_file(uploaded_file, new_image_path)
                if saved_filename:
                    image_path = saved_filename
        else:
            # Use form value if no file uploaded
            image_path = request.form.get('image_path', image_path)

        cursor.execute(
            'UPDATE task SET title = ?, description = ?, theorem_type = ?, difficulty = ?, hints = ?, solution_type = ?, solution = ?, image_path = ? WHERE id = ?',
            (request.form.get('title'), request.form.get('description'), request.form.get('theorem_type'),
             request.form.get('difficulty'), json.dumps(hints), request.form.get('solution_type', 'solution'),
             request.form.get('solution'), image_path, task_id)
        )
        db.commit()
        return redirect(url_for('add_task'))

    return render_template('admin/task_form.html', task=task)


@app.route('/add-task/<int:task_id>/delete', methods=['POST'])
def add_task_delete(task_id):
    """Delete task"""
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute('SELECT id FROM task WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        if not task:
            return redirect(url_for('add_task'))

        # Explicitly remove dependent records first.
        # This keeps deletion working even if the existing SQLite database
        # was created before ON DELETE CASCADE was added to the schema.
        cursor.execute('DELETE FROM user_task WHERE task_id = ?', (task_id,))
        cursor.execute('DELETE FROM task WHERE id = ?', (task_id,))
        db.commit()
    except sqlite3.IntegrityError as e:
        db.rollback()
        app.logger.error(f'Error deleting task {task_id}: {str(e)}')
        return jsonify({
            'error': 'Не удалось удалить задачу',
            'message': 'Сначала удалите связанные записи'
        }), 400
    except Exception as e:
        db.rollback()
        app.logger.error(f'Unexpected error deleting task {task_id}: {str(e)}')
        return jsonify({
            'error': 'Произошла ошибка',
            'message': 'Ошибка при удалении задачи'
        }), 500

    return redirect(url_for('add_task'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
