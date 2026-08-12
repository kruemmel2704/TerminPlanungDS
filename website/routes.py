from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .models import Poll, Option, Vote, User
from . import db
from .calendar_utils import create_league_calendar, add_event_to_calendar
from .whatsapp import wa_client
from datetime import datetime, timedelta

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
        poll_type = request.form.get('poll_type', 'single')
        title = request.form.get('title')
        description = request.form.get('description')
        deadline_str = request.form.get('deadline')

        parsed_options = []

        if poll_type == 'liga':
            liga_start_date_str = request.form.get('liga_start_date')
            if liga_start_date_str:
                try:
                    start_date = datetime.strptime(liga_start_date_str, '%Y-%m-%d')
                    for i in range(5):
                        day = start_date + timedelta(days=i)
                        s_dt = day.replace(hour=20, minute=30, second=0, microsecond=0)
                        e_dt = day.replace(hour=21, minute=30, second=0, microsecond=0)
                        parsed_options.append((s_dt, e_dt))
                except ValueError:
                    pass
        else: # single / tcw
            single_dates = request.form.getlist('single_date')
            for d_str in single_dates:
                if d_str:
                    try:
                        day = datetime.strptime(d_str, '%Y-%m-%d')
                        s_dt = day.replace(hour=20, minute=30, second=0, microsecond=0)
                        e_dt = day.replace(hour=21, minute=30, second=0, microsecond=0)
                        parsed_options.append((s_dt, e_dt))
                    except ValueError:
                        pass

        if not title or not deadline_str or not parsed_options:
            flash('Bitte gib einen Titel, eine Deadline und mindestens einen gültigen Terminvorschlag an!', category='error')
        else:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
                new_poll = Poll(title=title, description=description, deadline=deadline, poll_type=poll_type)
                db.session.add(new_poll)
                db.session.flush()

                for s_dt, e_dt in parsed_options:
                    new_opt = Option(poll_id=new_poll.id, start_time=s_dt, end_time=e_dt)
                    db.session.add(new_opt)
                
                db.session.commit()
                
                # WhatsApp Push Notification
                if current_user.whatsapp_chat_id:
                    vote_url = url_for('routes.vote', poll_id=new_poll.id, _external=True)
                    push_msg = f"🚀 *Neue Abstimmung gestartet: {new_poll.title}*\n\n"
                    if new_poll.description:
                        push_msg += f"{new_poll.description}\n\n"
                    push_msg += f"Bitte hier abstimmen:\n{vote_url}"
                    wa_client.send_message(current_user.whatsapp_chat_id, push_msg)

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
        flash(f'Abstimmung "{poll.title}" wurde beendet. Sie liegt nun unter "Abgeschlossene Events", wo du das Roster festlegen kannst!', category='success')
    
    return redirect(url_for('routes.admin_dashboard'))

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
        calendar_success = False
        calendar_attempted = False
        
        if admin and admin.google_token:
            calendar_attempted = True
            if not admin.google_calendar_id:
                cal_id = create_league_calendar(admin)
                if cal_id:
                    admin.google_calendar_id = cal_id
                    db.session.commit()
            
            if admin.google_calendar_id:
                # Create a temporary option object for the calendar utility
                from collections import namedtuple
                TempOpt = namedtuple('TempOpt', ['start_time', 'end_time'])
                temp_opt = TempOpt(start_time=final_start, end_time=final_end)
                
                roster_desc = f"🛡️ War Orga: {poll.war_orga}\n⚔️ Spieler: {poll.players}\n🔄 Ersatz: {poll.substitutes}"
                calendar_success = add_event_to_calendar(admin, temp_opt, f"{poll.title} - FINAL", roster_desc)
        
        db.session.commit()
        
        if calendar_attempted and not calendar_success:
            flash('Termin wurde final bestätigt, ABER das Eintragen in den Kalender ist fehlgeschlagen (Google-Token abgelaufen?). Bitte erneut in den Einstellungen anmelden.', category='warning')
        elif calendar_success:
            flash('Termin wurde final bestätigt und im Kalender eingetragen!', category='success')
        else:
            flash('Termin wurde final bestätigt!', category='success')
            
        return redirect(url_for('routes.results', poll_id=poll.id))

    return render_template("confirm_poll.html", poll=poll, winner=winner, user=current_user)

@routes.route('/admin/reset/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def reset_poll(poll_id):
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    poll = Poll.query.get_or_404(poll_id)
    
    if request.method == 'POST':
        new_deadline_str = request.form.get('deadline')
        if not new_deadline_str:
            flash('Bitte gib eine gültige neue Deadline an!', category='error')
            return redirect(url_for('routes.reset_poll', poll_id=poll.id))
            
        try:
            new_deadline = datetime.strptime(new_deadline_str, '%Y-%m-%dT%H:%M')
            poll.deadline = new_deadline
            poll.status = 'voting'
            poll.is_active = True
            poll.winner_option_id = None
            
            # Delete previous votes
            for opt in poll.options:
                Vote.query.filter_by(option_id=opt.id).delete()
                
            db.session.commit()
            flash('Abstimmung wurde erfolgreich mit neuer Deadline zurückgesetzt und gestartet!', category='success')
            return redirect(url_for('routes.admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Fehler beim Zurücksetzen: {str(e)}', category='error')
            
    return render_template('reset_poll.html', poll=poll, user=current_user)

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

    # Notify creator if poll was created via WhatsApp
    if poll.whatsapp_creator_chat_id:
        from website.whatsapp import format_option_for_whatsapp, wa_client
        from flask import url_for, current_app
        
        # Build results message
        msg = f"📊 *Abstimmung abgeschlossen: {poll.title}*\n\n"
        msg += "Ergebnisse:\n"
        
        # Sort options by vote count
        sorted_opts = []
        for opt in poll.options:
            sorted_opts.append((opt, len(opt.votes)))
        sorted_opts.sort(key=lambda x: x[1], reverse=True)
        
        for opt, count in sorted_opts:
            opt_str = format_option_for_whatsapp(opt)
            voters = ", ".join([v.user_name for v in opt.votes])
            if voters:
                msg += f"• {opt_str}: *{count} Stimme(n)* ({voters})\n"
            else:
                msg += f"• {opt_str}: *{count} Stimme(n)*\n"
                
        if winner_opt:
            winner_str = format_option_for_whatsapp(winner_opt)
            msg += f"\n🏆 *Gewinner-Termin:* {winner_str}\n"
            
        server_name = request.host_url if request else 'http://localhost:5000/'
        roster_url = f"{server_name}#/admin/confirm/{poll.id}"
            
        msg += f"\n🛡️ Erstelle das Roster auf folgender Seite:\n{roster_url}"
        
        # Send via WhatsApp client
        wa_client.send_message(poll.whatsapp_creator_chat_id, msg)


# --- REST API ENDPOINTS FOR REACT ---

def serialize_poll(poll):
    return {
        'id': poll.id,
        'title': poll.title,
        'description': poll.description,
        'created_at': poll.created_at.isoformat() if poll.created_at else None,
        'deadline': poll.deadline.isoformat() if poll.deadline else None,
        'is_active': poll.is_active,
        'status': poll.status,
        'poll_type': poll.poll_type,
        'winner_option_id': poll.winner_option_id,
        'war_orga': poll.war_orga,
        'players': poll.players,
        'substitutes': poll.substitutes,
        'options': [{
            'id': opt.id,
            'poll_id': opt.poll_id,
            'start_time': opt.start_time.isoformat(),
            'end_time': opt.end_time.isoformat(),
            'votes': [{
                'id': v.id,
                'option_id': v.option_id,
                'user_id': v.user_id,
                'user_name': v.user_name,
                'is_whatsapp': v.is_whatsapp
            } for v in opt.votes]
        } for opt in poll.options],
        'unique_voter_count': poll.unique_voter_count,
        'unique_voter_names': poll.unique_voter_names
    }

@routes.route('/api/polls')
@login_required
def api_polls():
    polls = Poll.query.all()
    return jsonify([serialize_poll(p) for p in polls])

@routes.route('/api/polls/<int:poll_id>')
@login_required
def api_poll_detail(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    # Check if poll is expired
    if poll.is_active and datetime.now() > poll.deadline:
        finalize_poll(poll)
    return jsonify(serialize_poll(poll))

@routes.route('/api/polls/<int:poll_id>/vote', methods=['POST'])
@login_required
def api_vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    if not poll.is_active:
        return jsonify({'message': 'Diese Abstimmung ist bereits beendet!'}), 400
        
    data = request.json
    selected_option_ids = data.get('option_ids', [])
    
    if not selected_option_ids:
        return jsonify({'message': 'Bitte wähle mindestens einen Termin aus!'}), 400
        
    success_count = 0
    for opt_id in selected_option_ids:
        existing_vote = Vote.query.filter_by(user_id=current_user.id, option_id=opt_id).first()
        if not existing_vote:
            new_vote = Vote(option_id=opt_id, user_id=current_user.id, user_name=current_user.username)
            db.session.add(new_vote)
            success_count += 1
            
    if success_count > 0:
        db.session.commit()
        return jsonify({'message': f'{success_count} Stimme(n) erfolgreich gespeichert!'})
    else:
        return jsonify({'message': 'Du hast bereits für alle ausgewählten Termine abgestimmt!'}), 400

@routes.route('/api/polls/create', methods=['POST'])
@login_required
def api_create_poll():
    if not current_user.is_admin:
        return jsonify({'message': 'Kein Zugriff!'}), 403
        
    data = request.json
    poll_type = data.get('poll_type', 'single')
    title = data.get('title')
    description = data.get('description')
    deadline_str = data.get('deadline')
    
    parsed_options = []
    
    if poll_type == 'liga':
        liga_start_date_str = data.get('liga_start_date')
        if liga_start_date_str:
            try:
                start_date = datetime.strptime(liga_start_date_str, '%Y-%m-%d')
                for i in range(5):
                    day = start_date + timedelta(days=i)
                    s_dt = day.replace(hour=20, minute=30, second=0, microsecond=0)
                    e_dt = day.replace(hour=21, minute=30, second=0, microsecond=0)
                    parsed_options.append((s_dt, e_dt))
            except ValueError:
                pass
    else:
        single_dates = data.get('single_dates', [])
        for d_str in single_dates:
            if d_str:
                try:
                    day = datetime.strptime(d_str, '%Y-%m-%d')
                    s_dt = day.replace(hour=20, minute=30, second=0, microsecond=0)
                    e_dt = day.replace(hour=21, minute=30, second=0, microsecond=0)
                    parsed_options.append((s_dt, e_dt))
                except ValueError:
                    pass
                    
    if not title or not deadline_str or not parsed_options:
        return jsonify({'message': 'Bitte gib einen Titel, eine Deadline und mindestens einen gültigen Terminvorschlag an!'}), 400
        
    try:
        deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        new_poll = Poll(title=title, description=description, deadline=deadline, poll_type=poll_type)
        db.session.add(new_poll)
        db.session.flush()
        
        for s_dt, e_dt in parsed_options:
            new_opt = Option(poll_id=new_poll.id, start_time=s_dt, end_time=e_dt)
            db.session.add(new_opt)
            
        db.session.commit()
        
        # WhatsApp Push Notification
        if current_user.whatsapp_chat_id:
            vote_url = request.host_url + f"#/vote/{new_poll.id}"
            push_msg = f"🚀 *Neue Abstimmung gestartet: {new_poll.title}*\n\n"
            if new_poll.description:
                push_msg += f"{new_poll.description}\n\n"
            push_msg += f"Bitte hier abstimmen:\n{vote_url}"
            wa_client.send_message(current_user.whatsapp_chat_id, push_msg)
            
        return jsonify({'message': 'Abstimmung erfolgreich erstellt!', 'poll_id': new_poll.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Fehler beim Speichern: {str(e)}'}), 500

@routes.route('/api/polls/<int:poll_id>/finalize', methods=['POST'])
@login_required
def api_finalize(poll_id):
    if not current_user.is_admin:
        return jsonify({'message': 'Kein Zugriff!'}), 403
    poll = Poll.query.get_or_404(poll_id)
    if poll.status == 'voting':
        finalize_poll(poll)
    return jsonify({'message': f'Abstimmung "{poll.title}" wurde beendet.'})

@routes.route('/api/polls/<int:poll_id>/confirm', methods=['POST'])
@login_required
def api_confirm_poll(poll_id):
    if not current_user.is_admin:
        return jsonify({'message': 'Kein Zugriff!'}), 403
        
    poll = Poll.query.get_or_404(poll_id)
    data = request.json
    
    poll.war_orga = data.get('war_orga')
    poll.players = data.get('players')
    poll.substitutes = data.get('substitutes')
    poll.status = 'finalized'
    
    final_start = datetime.strptime(data.get('final_start'), '%Y-%m-%dT%H:%M')
    final_end = datetime.strptime(data.get('final_end'), '%Y-%m-%dT%H:%M')
    
    admin = User.query.filter_by(is_admin=True).first()
    calendar_success = False
    calendar_attempted = False
    
    if admin and admin.google_token:
        calendar_attempted = True
        if not admin.google_calendar_id:
            cal_id = create_league_calendar(admin)
            if cal_id:
                admin.google_calendar_id = cal_id
                db.session.commit()
                
        if admin.google_calendar_id:
            from collections import namedtuple
            TempOpt = namedtuple('TempOpt', ['start_time', 'end_time'])
            temp_opt = TempOpt(start_time=final_start, end_time=final_end)
            
            roster_desc = f"🛡️ War Orga: {poll.war_orga}\n⚔️ Spieler: {poll.players}\n🔄 Ersatz: {poll.substitutes}"
            calendar_success = add_event_to_calendar(admin, temp_opt, f"{poll.title} - FINAL", roster_desc)
            
    db.session.commit()
    
    calendar_error = calendar_attempted and not calendar_success
    msg = 'Termin wurde final bestätigt!'
    if calendar_error:
        msg = 'Termin wurde final bestätigt, ABER das Eintragen in den Kalender ist fehlgeschlagen (Google-Token abgelaufen?). Bitte erneut in den Einstellungen anmelden.'
    elif calendar_success:
        msg = 'Termin wurde final bestätigt und im Kalender eingetragen!'
        
    return jsonify({
        'message': msg,
        'calendar_error': calendar_error
    })

@routes.route('/api/polls/<int:poll_id>/reset', methods=['POST'])
@login_required
def api_reset(poll_id):
    if not current_user.is_admin:
        return jsonify({'message': 'Kein Zugriff!'}), 403
        
    poll = Poll.query.get_or_404(poll_id)
    data = request.json
    new_deadline_str = data.get('deadline')
    
    if not new_deadline_str:
        return jsonify({'message': 'Bitte gib eine gültige neue Deadline an!'}), 400
        
    try:
        new_deadline = datetime.strptime(new_deadline_str, '%Y-%m-%dT%H:%M')
        poll.deadline = new_deadline
        poll.status = 'voting'
        poll.is_active = True
        poll.winner_option_id = None
        
        # Delete previous votes
        for opt in poll.options:
            Vote.query.filter_by(option_id=opt.id).delete()
            
        db.session.commit()
        return jsonify({'message': 'Abstimmung wurde erfolgreich mit neuer Deadline zurückgesetzt und gestartet!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Fehler beim Zurücksetzen: {str(e)}'}), 500
