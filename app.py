from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from database import init_db, get_db
import os

app = Flask(__name__)
app.secret_key = 'studybuddy_secret_key_2024'

# Инициализация БД при старте
with app.app_context():
    init_db()

# ══════════════════════════════════════
# ГЛАВНАЯ СТРАНИЦА
# ══════════════════════════════════════
@app.route('/')
def index():
    return render_template('index.html')

# ══════════════════════════════════════
# API: АУТЕНТИФИКАЦИЯ
# ══════════════════════════════════════
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    name     = data.get('name', '').strip()
    surname  = data.get('surname', '').strip()
    email    = data.get('email', '').strip()
    password = data.get('password', '')
    grade    = data.get('grade', '')
    is_tutor = data.get('is_tutor', False)
    subjects = data.get('subjects', '')
    bio      = data.get('bio', '')

    if not name or not email or not password:
        return jsonify({'error': 'Заполни все поля!'}), 400

    db = get_db()
    existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    if existing:
        return jsonify({'error': 'Email уже занят'}), 400

    db.execute('''
        INSERT INTO users (name, surname, email, password, grade, is_tutor, subjects, bio, emoji, rating, sessions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (name, surname, email, password, grade, int(is_tutor),
          subjects if is_tutor else '', bio if is_tutor else '',
          name[0].upper(), 5.0, 0))
    db.commit()

    user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    session['user_id'] = user['id']
    return jsonify({'success': True, 'user': dict(user)})


@app.route('/api/login', methods=['POST'])
def login():
    data     = request.get_json()
    email    = data.get('email', '').strip()
    password = data.get('password', '')

    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE email = ? AND password = ?',
                      (email, password)).fetchone()
    if not user:
        return jsonify({'error': 'Неверный email или пароль'}), 401

    session['user_id'] = user['id']
    return jsonify({'success': True, 'user': dict(user)})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'success': True})


@app.route('/api/me')
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'user': None})
    db   = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        return jsonify({'user': None})
    u = dict(user)
    # Расписание
    schedule_rows = db.execute(
        'SELECT day, time FROM schedules WHERE user_id = ?', (user_id,)
    ).fetchall()
    schedule = {}
    for row in schedule_rows:
        schedule.setdefault(row['day'], []).append(row['time'])
    u['schedule'] = schedule
    u['subjects'] = [s.strip() for s in (u.get('subjects') or '').split(',') if s.strip()]
    return jsonify({'user': u})

# ══════════════════════════════════════
# API: ТЬЮТОРЫ
# ══════════════════════════════════════
@app.route('/api/tutors')
def get_tutors():
    subject = request.args.get('subject', 'all')
    db      = get_db()
    users   = db.execute('SELECT * FROM users WHERE is_tutor = 1').fetchall()
    result  = []
    for u in users:
        tutor = dict(u)
        subj_list = [s.strip() for s in (tutor.get('subjects') or '').split(',') if s.strip()]
        if subject != 'all' and subject not in subj_list:
            continue
        tutor['subjects'] = subj_list

        # Расписание тьютора
        schedule_rows = db.execute(
            'SELECT day, time FROM schedules WHERE user_id = ?', (tutor['id'],)
        ).fetchall()
        schedule = {}
        for row in schedule_rows:
            schedule.setdefault(row['day'], []).append(row['time'])
        tutor['schedule'] = schedule
        result.append(tutor)
    return jsonify({'tutors': result})


@app.route('/api/stats')
def stats():
    db       = get_db()
    tutors   = db.execute('SELECT COUNT(*) FROM users WHERE is_tutor = 1').fetchone()[0]
    sessions = db.execute('SELECT COUNT(*) FROM bookings').fetchone()[0]
    subjects_raw = db.execute('SELECT subjects FROM users WHERE is_tutor = 1').fetchall()
    all_subj = set()
    for row in subjects_raw:
        for s in (row['subjects'] or '').split(','):
            if s.strip():
                all_subj.add(s.strip())
    return jsonify({'tutors': tutors, 'sessions': sessions + 47, 'subjects': len(all_subj) or 8})

# ══════════════════════════════════════
# API: РАСПИСАНИЕ
# ══════════════════════════════════════
@app.route('/api/schedule/save', methods=['POST'])
def save_schedule():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401

    data = request.get_json()
    days  = data.get('days', [])
    times = data.get('times', [])

    db = get_db()
    db.execute('DELETE FROM schedules WHERE user_id = ?', (user_id,))
    for day in days:
        for time in times:
            db.execute('INSERT INTO schedules (user_id, day, time) VALUES (?, ?, ?)',
                       (user_id, day, time))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/schedule/all')
def schedule_all():
    db   = get_db()
    rows = db.execute('''
        SELECT s.day, s.time, u.id as tutor_id, u.name, u.surname, u.subjects,
               b.id as booking_id, bu.name as student_name
        FROM schedules s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN bookings b ON b.tutor_id = u.id AND b.day = s.day AND b.time = s.time
        LEFT JOIN users bu ON b.student_id = bu.id
        ORDER BY s.day, s.time
    ''').fetchall()

    result = []
    for r in rows:
        item = dict(r)
        item['subjects'] = [s.strip() for s in (item.get('subjects') or '').split(',') if s.strip()]
        result.append(item)
    return jsonify({'slots': result})

# ══════════════════════════════════════
# API: БРОНИРОВАНИЕ
# ══════════════════════════════════════
@app.route('/api/book', methods=['POST'])
def book():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Войди в аккаунт'}), 401

    data     = request.get_json()
    tutor_id = data.get('tutor_id')
    day      = data.get('day')
    time     = data.get('time')
    subject  = data.get('subject')
    comment  = data.get('comment', '')

    db = get_db()
    existing = db.execute(
        'SELECT id FROM bookings WHERE tutor_id = ? AND day = ? AND time = ?',
        (tutor_id, day, time)
    ).fetchone()
    if existing:
        return jsonify({'error': 'Это время уже занято!'}), 400

    db.execute('''
        INSERT INTO bookings (tutor_id, student_id, day, time, subject, comment)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tutor_id, user_id, day, time, subject, comment))
    db.execute('UPDATE users SET sessions = sessions + 1 WHERE id = ?', (tutor_id,))
    db.commit()
    return jsonify({'success': True})


@app.route('/api/my_bookings')
def my_bookings():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'as_student': [], 'as_tutor': []})

    db = get_db()
    as_student = db.execute('''
        SELECT b.*, u.name as tutor_name, u.surname as tutor_surname
        FROM bookings b JOIN users u ON b.tutor_id = u.id
        WHERE b.student_id = ?
    ''', (user_id,)).fetchall()

    as_tutor = db.execute('''
        SELECT b.*, u.name as student_name, u.surname as student_surname
        FROM bookings b JOIN users u ON b.student_id = u.id
        WHERE b.tutor_id = ?
    ''', (user_id,)).fetchall()

    return jsonify({
        'as_student': [dict(r) for r in as_student],
        'as_tutor':   [dict(r) for r in as_tutor]
    })


# ══════════════════════════════════════
# API: СТАТЬ ТЬЮТОРОМ
# ══════════════════════════════════════
@app.route('/api/become_tutor', methods=['POST'])
def become_tutor():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Не авторизован'}), 401
    db = get_db()
    db.execute('UPDATE users SET is_tutor = 1 WHERE id = ?', (user_id,))
    db.commit()
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, port=5000)