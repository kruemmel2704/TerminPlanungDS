from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .models import Poll, Option, Vote, User
from . import db
from .calendar_utils import create_league_calendar, add_event_to_calendar
from datetime import datetime

routes = Blueprint('routes', __name__)

@routes.route('/')
@login_required
def home():
    polls = Poll.query.filter_by(is_active=True).all()
    return render_template("home.html", polls=polls, user=current_user)

@routes.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Kein Zugriff!', category='error')
        return redirect(url_for('routes.home'))

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        deadline_str = request.form.get('deadline')
        option_starts = request.form.getlist('option_start')
        option_ends = request.form.getlist('option_end')

        # Check if at least one option is fully filled
        valid_options = any(s and e for s, e in zip(option_starts, option_ends))

        if not title or not deadline_str or not valid_options:
            flash('Bitte gib einen Titel, eine Deadline und mindestens einen vollständigen Terminvorschlag an!', category='error')
        else:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
                new_poll = Poll(title=title, description=description, deadline=deadline)
                db.session.add(new_poll)
                db.session.flush()

                for start, end in zip(option_starts, option_ends):
                    if start and end:
                        s_dt = datetime.strptime(start, '%Y-%m-%dT%H:%M')
                        e_dt = datetime.strptime(end, '%Y-%m-%dT%H:%M')
                        new_opt = Option(poll_id=new_poll.id, start_time=s_dt, end_time=e_dt)
                        db.session.add(new_opt)
                
                db.session.commit()
                flash('Abstimmung erfolgreich erstellt!', category='success')
                return redirect(url_for('routes.admin_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f'Fehler beim Speichern: {str(e)}', category='error')

    active_polls = Poll.query.filter_by(is_active=True).all()
    finished_polls = Poll.query.filter_by(is_active=False).all()
    return render_template("admin.html", active_polls=active_polls, finished_polls=finished_polls, user=current_user)

@routes.route('/vote/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    
    # Check if poll is expired
    if poll.is_active and datetime.now() > poll.deadline:
        finalize_poll(poll)

    if not poll.is_active:
        return redirect(url_for('routes.results', poll_id=poll.id))

    if request.method == 'POST':
        selected_option_ids = request.form.getlist('option_ids')

        if not selected_option_ids:
            flash('Bitte wähle mindestens einen Termin aus!', category='error')
        else:
            success_count = 0
            for opt_id in selected_option_ids:
                # Check if already voted for THIS option
                existing_vote = Vote.query.filter_by(user_id=current_user.id, option_id=opt_id).first()
                if existing_vote:
                    option = Option.query.get(opt_id)
                    flash(f'Für den Termin am {option.start_time.strftime("%d.%m.%Y")} hast du bereits abgestimmt!', category='error')
                else:
                    new_vote = Vote(option_id=opt_id, user_id=current_user.id, user_name=current_user.username)
                    db.session.add(new_vote)
                    success_count += 1
            
            if success_count > 0:
                db.session.commit()
                flash(f'{success_count} Stimme(n) erfolgreich gespeichert!', category='success')
                return redirect(url_for('routes.home'))

    return render_template("vote.html", poll=poll, user=current_user)

@routes.route('/admin/finalize/<int:poll_id>')
@login_required
def manual_finalize(poll_id):
    if not current_user.is_admin:
        flash('Kein Zugriff!', category='error')
        return redirect(url_for('routes.home'))
    
    poll = Poll.query.get_or_404(poll_id)
    if poll.status == 'voting':
        finalize_poll(poll)
        flash(f'Abstimmung "{poll.title}" wurde beendet. Bitte jetzt Roster festlegen!', category='success')
    
    return redirect(url_for('routes.confirm_poll', poll_id=poll.id))

@routes.route('/admin/confirm/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def confirm_poll(poll_id):
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    poll = Poll.query.get_or_404(poll_id)
    
    # Calculate winner for display
    results_data = []
    for option in poll.options:
        voters = [v.user_name for v in option.votes]
        results_data.append({
            'option': option,
            'votes_count': len(option.votes),
            'voters': voters
        })
    results_data.sort(key=lambda x: x['votes_count'], reverse=True)
    winner = results_data[0] if results_data else None

    if request.method == 'POST':
        poll.war_orga = request.form.get('war_orga')
        poll.players = request.form.get('players')
        poll.substitutes = request.form.get('substitutes')
        poll.status = 'finalized'
        
        # Override dates if admin changed them
        final_start = datetime.strptime(request.form.get('final_start'), '%Y-%m-%dT%H:%M')
        final_end = datetime.strptime(request.form.get('final_end'), '%Y-%m-%dT%H:%M')
        
        # Google Calendar Integration
        admin = User.query.filter_by(is_admin=True).first()
        if admin and admin.google_token:
            if not admin.google_calendar_id:
                cal_id = create_league_calendar(admin)
                admin.google_calendar_id = cal_id
                db.session.commit()
            
            if admin.google_calendar_id:
                # Create a temporary option object for the calendar utility
                from collections import namedtuple
                TempOpt = namedtuple('TempOpt', ['start_time', 'end_time'])
                temp_opt = TempOpt(start_time=final_start, end_time=final_end)
                
                roster_desc = f"🛡️ War Orga: {poll.war_orga}\n⚔️ Spieler: {poll.players}\n🔄 Ersatz: {poll.substitutes}"
                add_event_to_calendar(admin, temp_opt, f"{poll.title} - FINAL", roster_desc)
        
        db.session.commit()
        flash('Termin wurde final bestätigt und im Kalender eingetragen!', category='success')
        return redirect(url_for('routes.results', poll_id=poll.id))

    return render_template("confirm_poll.html", poll=poll, winner=winner, user=current_user)

@routes.route('/admin/reset/<int:poll_id>')
@login_required
def reset_poll(poll_id):
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    poll = Poll.query.get_or_404(poll_id)
    poll.status = 'voting'
    poll.is_active = True
    poll.winner_option_id = None
    # Delete previous votes? User might want to keep them or wipe. Usually reset means wipe.
    for opt in poll.options:
        Vote.query.filter_by(option_id=opt.id).delete()
        
    db.session.commit()
    flash('Abstimmung wurde zurückgesetzt und neu gestartet!', category='success')
    return redirect(url_for('routes.admin_dashboard'))

@routes.route('/results/<int:poll_id>')
@login_required
def results(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    if poll.status == 'voting' and datetime.now() > poll.deadline:
        finalize_poll(poll)
    
    # Get winner and voters
    results_data = []
    for option in poll.options:
        voters = [v.user_name for v in option.votes]
        results_data.append({
            'option': option,
            'votes_count': len(option.votes),
            'voters': voters
        })
    
    results_data.sort(key=lambda x: x['votes_count'], reverse=True)
    winner = results_data[0] if results_data else None

    return render_template("results.html", poll=poll, results=results_data, winner=winner, user=current_user)

def finalize_poll(poll):
    poll.is_active = False
    poll.status = 'pending'
    
    # Find winner (just to pre-select for admin)
    max_votes = -1
    winner_opt = None
    
    for opt in poll.options:
        count = len(opt.votes)
        if count > max_votes:
            max_votes = count
            winner_opt = opt
    
    if winner_opt:
        poll.winner_option_id = winner_opt.id
                
    db.session.commit()
