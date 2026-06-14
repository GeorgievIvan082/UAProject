from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from .models import Routine, RoutineTask
from . import db
from datetime import datetime
import json


views = Blueprint('views', __name__)


def validate_task_data(offset, position, action, duration, is_recurring=False, repeat_every=None):
    errors = []

    if offset is None:
        errors.append('Offset is required.')

    if position is None:
        errors.append('Position is required.')

    if duration is None or duration < 0:
        errors.append('Duration must be zero or greater.')

    if not action or len(action.strip()) == 0:
        errors.append('Action is required.')

    if is_recurring:
        if repeat_every is None or repeat_every < 1:
            errors.append('Repeat every must be a whole number of at least 1 hour.')

    return errors


@views.route('/')
@login_required
def home():
    routines = Routine.query.filter_by(user_id=current_user.id).order_by(Routine.created_at.desc()).all()
    return render_template('home.html', user=current_user, routines=routines)


@views.route('/routine/new', methods=['POST'])
@login_required
def create_routine():
    name = request.form.get('name')
    description = request.form.get('description')
    start_date_raw = request.form.get('start_date')
    end_date_raw = request.form.get('end_date')

    if not name or len(name.strip()) < 2:
        flash('Routine name must be at least 2 characters.', category='error')
        return redirect(url_for('views.home'))

    start_date = None
    end_date = None

    try:
        if start_date_raw:
            start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date()
        if end_date_raw:
            end_date = datetime.strptime(end_date_raw, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format.', category='error')
        return redirect(url_for('views.home'))

    if start_date and end_date and end_date < start_date:
        flash('End date cannot be before start date.', category='error')
        return redirect(url_for('views.home'))

    routine = Routine(
        name=name.strip(),
        description=description,
        start_date=start_date,
        end_date=end_date,
        user_id=current_user.id
    )

    db.session.add(routine)
    db.session.commit()

    flash('Routine created.', category='success')
    return redirect(url_for('views.routine_detail', routine_id=routine.id))


@views.route('/routine/<int:routine_id>', methods=['GET'])
@login_required
def routine_detail(routine_id):
    routine = Routine.query.filter_by(id=routine_id, user_id=current_user.id).first_or_404()
    return render_template('routine_detail.html', user=current_user, routine=routine)


@views.route('/routine/<int:routine_id>/task/add', methods=['POST'])
@login_required
def add_task(routine_id):
    routine = Routine.query.filter_by(id=routine_id, user_id=current_user.id).first_or_404()

    try:
        offset = float(request.form.get('offset') or 0)
        position = float(request.form.get('position'))
        duration = float(request.form.get('duration') or 0)
    except (ValueError, TypeError):
        flash('Offset, position, and duration must be valid numbers.', category='error')
        return redirect(url_for('views.routine_detail', routine_id=routine.id))

    action = (request.form.get('action') or '').strip()
    is_recurring = request.form.get('is_recurring') == 'on'
    repeat_every = request.form.get('repeat_every', type=int) if is_recurring else None
    repeat_unit = 'hour' if is_recurring else None

    errors = validate_task_data(offset, position, action, duration, is_recurring, repeat_every)

    if errors:
        for error in errors:
            flash(error, category='error')
        return redirect(url_for('views.routine_detail', routine_id=routine.id))

    next_order = len(routine.tasks) + 1

    task = RoutineTask(
        order_index=next_order,
        offset=offset,
        position=position,
        action=action,
        duration=duration,
        is_recurring=is_recurring,
        repeat_every=repeat_every,
        repeat_unit=repeat_unit,
        routine_id=routine.id
    )

    db.session.add(task)
    db.session.commit()

    flash('Task added to routine.', category='success')
    return redirect(url_for('views.routine_detail', routine_id=routine.id))


@views.route('/delete-task', methods=['POST'])
@login_required
def delete_task():
    data = request.get_json()
    task_id = data.get('taskId')
    task = RoutineTask.query.get(task_id)

    if task and task.routine.user_id == current_user.id:
        routine_id = task.routine.id
        db.session.delete(task)
        db.session.commit()

        remaining_tasks = RoutineTask.query.filter_by(routine_id=routine_id).order_by(RoutineTask.order_index).all()
        for index, item in enumerate(remaining_tasks, start=1):
            item.order_index = index
        db.session.commit()

        return jsonify({"success": True})

    return jsonify({"success": False}), 403


@views.route('/routine/<int:routine_id>/reorder-tasks', methods=['POST'])
@login_required
def reorder_tasks(routine_id):
    routine = Routine.query.filter_by(id=routine_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    task_ids = data.get('taskIds', [])

    if not task_ids:
        return jsonify({"success": False}), 400

    tasks = RoutineTask.query.filter_by(routine_id=routine.id).all()
    task_map = {task.id: task for task in tasks}

    for index, task_id in enumerate(task_ids, start=1):
        if task_id in task_map:
            task_map[task_id].order_index = index

    db.session.commit()
    return jsonify({"success": True})


@views.route('/routine/<int:routine_id>/validate')
@login_required
def validate_routine(routine_id):
    routine = Routine.query.filter_by(id=routine_id, user_id=current_user.id).first_or_404()
    errors = []

    if len(routine.tasks) == 0:
        errors.append('Routine has no tasks.')

    if routine.start_date and routine.end_date and routine.end_date < routine.start_date:
        errors.append('Routine end date cannot be before start date.')

    for task in routine.tasks:
        task_errors = validate_task_data(
            task.offset,
            task.position,
            task.action,
            task.duration,
            task.is_recurring,
            task.repeat_every
        )
        for error in task_errors:
            errors.append(f'Task {task.order_index}: {error}')

    if errors:
        for error in errors:
            flash(error, category='error')
    else:
        flash('Routine is valid and ready for execution.', category='success')

    return redirect(url_for('views.routine_detail', routine_id=routine.id))