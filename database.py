import sqlite3
from flask import g
import os

DATABASE = os.path.join(os.path.dirname(__file__), 'studybuddy.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            surname  TEXT DEFAULT '',
            email    TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            grade    TEXT DEFAULT '',
            is_tutor INTEGER DEFAULT 0,
            subjects TEXT DEFAULT '',
            bio      TEXT DEFAULT '',
            emoji    TEXT DEFAULT '?',
            rating   REAL DEFAULT 5.0,
            sessions INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS schedules (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day     TEXT NOT NULL,
            time    TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id   INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            day        TEXT NOT NULL,
            time       TEXT NOT NULL,
            subject    TEXT DEFAULT '',
            comment    TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tutor_id)   REFERENCES users(id),
            FOREIGN KEY (student_id) REFERENCES users(id)
        );
    ''')

    # Добавить демо-данные если таблица пустая
    count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    if count == 0:
        demo_users = [
            ('Алия',   'Сейткали', 'a@demo.kz', 'demo', '10 класс', 1, 'Математика,Физика',
             'Олимпиадник, объясню сложные темы просто', 'А', 4.9, 23),
            ('Данияр', 'Жанов',    'd@demo.kz', 'demo', '11 класс', 1, 'Химия,Биология',
             'Готовлюсь к мед. университету, помогу с ЕНТ', 'Д', 4.7, 15),
            ('Камила', 'Нурова',   'k@demo.kz', 'demo', '11 класс', 1, 'Английский,История',
             'Upper-Intermediate, могу объяснить грамматику', 'К', 4.8, 18),
            ('Арман',  'Токов',    'ar@demo.kz','demo', '9 класс',  1, 'Математика,История',
             'Помог 10+ ученикам в прошлом году',           'Р', 4.6, 8),
        ]
        for u in demo_users:
            db.execute('''
                INSERT INTO users (name,surname,email,password,grade,is_tutor,subjects,bio,emoji,rating,sessions)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ''', u)
        db.commit()

        # Расписание для демо-тьюторов
        schedules = [
            (1, 'Пн', ['14:00','15:00','16:00']),
            (1, 'Ср', ['13:00','14:00']),
            (1, 'Пт', ['15:00','16:00','17:00']),
            (2, 'Вт', ['10:00','11:00','13:00']),
            (2, 'Чт', ['15:00','16:00']),
            (2, 'Сб', ['10:00','12:00']),
            (3, 'Пн', ['15:00','16:00']),
            (3, 'Ср', ['13:00','14:00']),
            (3, 'Пт', ['12:00','13:00','15:00']),
            (4, 'Вт', ['14:00','15:00']),
            (4, 'Чт', ['10:00','11:00']),
            (4, 'Сб', ['13:00','14:00']),
        ]
        for user_id, day, times in schedules:
            for time in times:
                db.execute('INSERT INTO schedules (user_id, day, time) VALUES (?,?,?)',
                           (user_id, day, time))
        db.commit()
    db.close()