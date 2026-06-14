from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class Routine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500))
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    tasks = db.relationship(
        'RoutineTask',
        backref='routine',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='RoutineTask.order_index'
    )

class RoutineTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_index = db.Column(db.Integer, nullable=False)
    offset = db.Column(db.Float, nullable=False, default=0)
    position = db.Column(db.Float, nullable=False)
    action = db.Column(db.String(50), nullable=False)
    duration = db.Column(db.Float, nullable=False, default=0)
    routine_id = db.Column(db.Integer, db.ForeignKey('routine.id'), nullable=False)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(255))
    first_name = db.Column(db.String(150))
    routines = db.relationship('Routine')