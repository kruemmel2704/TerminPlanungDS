from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .whatsapp_utils import WhatsAppClient, normalize_id
from .models import Poll, Option, Vote, User, WhatsAppState
from . import db
from datetime import datetime, timedelta
import json

whatsapp = Blueprint('whatsapp', __name__)
wa_client = WhatsAppClient()

@whatsapp.route('/whatsapp')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Kein Zugriff!', category='error')
        return redirect(url_for('routes.home'))
    
    if not wa_client.is_configured():
        flash('WhatsApp-API ist noch nicht in der .env konfiguriert!', category='warning')
        return render_template("whatsapp.html", status="unconfigured", user=current_user)

    state_resp = wa_client.get_status()
    state = state_resp.get('stateInstance')
    
    qr_data = None
    if state == 'notAuthorized':
        qr_resp = wa_client.get_qr_code()
        if qr_resp:
            qr_data = qr_resp.get('message')

    groups = []
    if state in ['online', 'authorized']:
        groups = wa_client.get_groups()

    return render_template("whatsapp.html", 
                           status=state, 
                           qr_data=qr_data, 
                           groups=groups,
                           user=current_user)

@whatsapp.route('/whatsapp/set_default', methods=['POST'])
@login_required
def set_default_chat():
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    chat_id = request.form.get('chat_id')
    chat_name = request.form.get('chat_name')
    
    if chat_id:
        current_user.whatsapp_chat_id = chat_id
        current_user.whatsapp_chat_name = chat_name
        db.session.commit()
        flash(f'Standard-Chat "{chat_name}" wurde gespeichert.', category='success')
    else:
        flash('Fehler beim Speichern des Standard-Chats.', category='error')
        
    return redirect(url_for('whatsapp.dashboard'))

@whatsapp.route('/whatsapp/set_admin_chat', methods=['POST'])
@login_required
def set_admin_chat():
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    chat_id = request.form.get('admin_chat_id')
    chat_name = request.form.get('admin_chat_name')
    
    if chat_id:
        current_user.whatsapp_admin_chat_id = chat_id
        current_user.whatsapp_admin_chat_name = chat_name
        db.session.commit()
        flash(f'Admin-Chat "{chat_name}" wurde gespeichert.', category='success')
    else:
        current_user.whatsapp_admin_chat_id = None
        current_user.whatsapp_admin_chat_name = None
        db.session.commit()
        flash('Admin-Chat wurde entfernt.', category='success')
        
    return redirect(url_for('whatsapp.dashboard'))

@whatsapp.route('/whatsapp/logout')
@login_required
def logout():
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    if wa_client.logout():
        flash('Erfolgreich von WhatsApp abgemeldet.', category='success')
    else:
        flash('Fehler beim Abmelden.', category='error')
    return redirect(url_for('whatsapp.dashboard'))

@whatsapp.route('/whatsapp/share/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def share_poll(poll_id):
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    poll = Poll.query.get_or_404(poll_id)
    
    # Check if authorized
    status_resp = wa_client.get_status()
    state = status_resp.get('stateInstance')
    if state not in ['online', 'authorized']:
        flash('Bitte verbinde zuerst deinen WhatsApp Account!', category='warning')
        return redirect(url_for('whatsapp.dashboard'))

    if request.method == 'POST':
        chat_id = request.form.get('chat_id')
        if not chat_id:
            flash('Bitte wähle eine Gruppe aus!', category='error')
        elif len(poll.options) == 0:
            flash('Diese Abstimmung hat keine Terminvorschläge!', category='error')
        else:
            # Construct reminder message
            vote_url = url_for('routes.vote', poll_id=poll.id, _external=True)
            message = f"🔔 *Reminder: Abstimmung für {poll.title}*\n\n"
            if poll.description:
                message += f"{poll.description}\n\n"
            message += f"Du hast noch nicht abgestimmt? Hier klicken:\n{vote_url}"
            
            if wa_client.send_message(chat_id, message):
                flash(f'Reminder wurde erfolgreich an WhatsApp gesendet!', category='success')
                return redirect(url_for('routes.admin_dashboard'))
            else:
                flash('Fehler beim Senden des Reminders.', category='error')

    groups = wa_client.get_groups()
    return render_template("whatsapp_share.html", poll=poll, groups=groups, user=current_user)

DE_DAYS = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}

def format_option_for_whatsapp(option):
    day_name = DE_DAYS[option.start_time.weekday()]
    return f"{day_name}. {option.start_time.strftime('%d.%m.%Y (%H:%M)')}"

def process_whatsapp_vote(poll_message_id, sender_jid, selected_options, display_name_override=None):
    poll_message_id = normalize_id(poll_message_id)
    sender_jid = normalize_id(sender_jid)
    poll = Poll.query.filter_by(whatsapp_poll_id=poll_message_id).first()
    if not poll:
        print(f"No poll found with whatsapp_poll_id={poll_message_id}")
        return False
        
    system_user = User.query.filter_by(discord_id='whatsapp_system').first()
    if not system_user:
        system_user = User(
            discord_id='whatsapp_system',
            username='WhatsApp System',
            is_admin=False
        )
        db.session.add(system_user)
        db.session.commit()
        
    if display_name_override:
        display_name = f"{display_name_override} (WhatsApp)"
    else:
        display_name = None
        contact_data = wa_client.get_contact(sender_jid)
        if contact_data:
            display_name = contact_data.get('name') or contact_data.get('pushname') or contact_data.get('shortName')
        
        if not display_name:
            phone = sender_jid.split('@')[0]
            display_name = f"+{phone} (WhatsApp)"
        else:
            display_name = f"{display_name} (WhatsApp)"
        
    options = poll.options
    option_ids = [opt.id for opt in options]
    Vote.query.filter(Vote.option_id.in_(option_ids), Vote.whatsapp_sender == sender_jid).delete(synchronize_session=False)
    db.session.commit()
    
    for opt in options:
        opt_str = format_option_for_whatsapp(opt).strip()
        if opt_str in selected_options:
            new_vote = Vote(
                option_id=opt.id,
                user_id=system_user.id,
                user_name=display_name,
                whatsapp_sender=sender_jid,
                is_whatsapp=True
            )
            db.session.add(new_vote)
            
    db.session.commit()
    return True

@whatsapp.route('/whatsapp/send_poll/<int:poll_id>', methods=['GET', 'POST'])
@login_required
def send_poll_view(poll_id):
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    poll = Poll.query.get_or_404(poll_id)
    
    status_resp = wa_client.get_status()
    state = status_resp.get('stateInstance')
    if state not in ['online', 'authorized']:
        flash('Bitte verbinde zuerst deinen WhatsApp Account!', category='warning')
        return redirect(url_for('whatsapp.dashboard'))

    if request.method == 'POST':
        chat_id = request.form.get('chat_id')
        if not chat_id:
            flash('Bitte wähle eine Gruppe aus!', category='error')
        elif len(poll.options) == 0:
            flash('Diese Abstimmung hat keine Terminvorschläge!', category='error')
        else:
            options_list = [format_option_for_whatsapp(opt) for opt in poll.options]
            poll_name = f"⚔️ Abstimmung: {poll.title}"
            if poll.description:
                poll_name += f"\n{poll.description}"
                
            response = wa_client.send_poll(chat_id, poll_name, options_list, multiple_answers=True)
            if response and response.get('id'):
                poll.whatsapp_poll_id = normalize_id(response.get('id'))
                db.session.commit()
                flash(f'WhatsApp-Umfrage wurde erfolgreich gestartet!', category='success')
                return redirect(url_for('routes.admin_dashboard'))
            else:
                flash('Fehler beim Starten der WhatsApp-Umfrage.', category='error')

    groups = wa_client.get_groups()
    return render_template("whatsapp_send_poll.html", poll=poll, groups=groups, user=current_user)

@whatsapp.route('/whatsapp/webhook', methods=['POST'])
def webhook():
    data = request.json or {}
    print(f"Received WAHA webhook: {data}")
    event = data.get('event')
    
    if event == 'message':
        payload = data.get('payload', {})
        sender_jid = normalize_id(payload.get('from'))
        chat_id = normalize_id(payload.get('chatId') or payload.get('from'))
        body = (payload.get('body') or "").strip()
        
        # Check if the chat where the message was received is a configured admin chat
        admin_user = User.query.filter_by(whatsapp_admin_chat_id=chat_id, is_admin=True).first()
        
        # Check if the admin sent /abstimmung
        if body.lower() == '/abstimmung':
            if not admin_user:
                wa_client.send_message(chat_id, "❌ Dieser Chat ist nicht als Admin-Chat autorisiert. Bitte konfiguriere ihn in den Einstellungen unter /whatsapp.")
                return jsonify({"status": "unauthorized"}), 200
                
            # Clear any existing state for this chat
            WhatsAppState.query.filter_by(chat_id=chat_id).delete()
            db.session.commit()
            
            # Start flow: send poll to select poll type
            new_state = WhatsAppState(
                chat_id=chat_id,
                sender_jid=sender_jid,
                state='awaiting_type'
            )
            db.session.add(new_state)
            db.session.commit()
            
            poll_name = "🏆 Wähle den Typ der Abstimmung:"
            options = ["🏆 Liga Spiel (5 Tage)", "⚔️ TCW / Single Event"]
            resp = wa_client.send_poll(chat_id, poll_name, options, multiple_answers=False)
            if resp and resp.get('id'):
                new_state.whatsapp_poll_id = normalize_id(resp.get('id'))
                db.session.commit()
            else:
                wa_client.send_message(chat_id, "❌ Fehler beim Senden der Typ-Auswahl-Umfrage. Bitte versuche es erneut.")
            return jsonify({"status": "success"}), 200
            
        # If not /abstimmung, check if this chat has an active setup state
        state_record = WhatsAppState.query.filter_by(chat_id=chat_id).first()
        if state_record:
            if state_record.state == 'awaiting_title':
                state_record.title = body
                state_record.state = 'awaiting_date'
                db.session.commit()
                
                if state_record.poll_type == 'liga':
                    prompt = (
                        f"Titel: *{body}*\n\n"
                        "Bitte gib das *Startdatum* für das Liga-Spiel an (Format: `TT.MM.JJJJ`, z.B. `26.05.2026`).\n"
                        "Der Bot generiert automatisch 5 Termine an aufeinanderfolgenden Tagen ab diesem Datum (jeweils um 20:30 Uhr)."
                    )
                else:
                    prompt = (
                        f"Titel: *{body}*\n\n"
                        "Bitte gib die *Termine* an (Format: `TT.MM.JJJJ`, mehrere durch Komma oder neue Zeile getrennt, z.B. `26.05.2026, 28.05.2026`).\n"
                        "Die Termine starten jeweils um 20:30 Uhr."
                    )
                wa_client.send_message(chat_id, prompt)
                return jsonify({"status": "success"}), 200
                
            elif state_record.state == 'awaiting_date':
                dates_list = []
                
                def parse_german_date(date_str):
                    date_str = date_str.strip()
                    for fmt in ('%d.%m.%Y', '%d.%m.%y', '%Y-%m-%d'):
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            pass
                    return None
                
                if state_record.poll_type == 'liga':
                    base_date = parse_german_date(body)
                    if not base_date:
                        wa_client.send_message(chat_id, "❌ *Ungültiges Datum.* Bitte verwende das Format `TT.MM.JJJJ` (z.B. `26.05.2026`):")
                        return jsonify({"status": "invalid_date"}), 200
                    
                    for i in range(5):
                        day = base_date + timedelta(days=i)
                        s_dt = day.replace(hour=20, minute=30, second=0, microsecond=0)
                        e_dt = day.replace(hour=21, minute=30, second=0, microsecond=0)
                        dates_list.append((s_dt.strftime('%Y-%m-%d %H:%M:%S'), e_dt.strftime('%Y-%m-%d %H:%M:%S')))
                else:
                    parts = []
                    for line in body.replace('\r', '\n').split('\n'):
                        for p in line.split(','):
                            p_clean = p.strip()
                            if p_clean:
                                parts.append(p_clean)
                    
                    for p in parts:
                        parsed_dt = parse_german_date(p)
                        if parsed_dt:
                            s_dt = parsed_dt.replace(hour=20, minute=30, second=0, microsecond=0)
                            e_dt = parsed_dt.replace(hour=21, minute=30, second=0, microsecond=0)
                            dates_list.append((s_dt.strftime('%Y-%m-%d %H:%M:%S'), e_dt.strftime('%Y-%m-%d %H:%M:%S')))
                            
                    if not dates_list:
                        wa_client.send_message(chat_id, "❌ *Keine gültigen Termine gefunden.* Bitte gib mindestens ein gültiges Datum im Format `TT.MM.JJJJ` an (mehrere durch Komma getrennt):")
                        return jsonify({"status": "invalid_date"}), 200
                
                state_record.dates = json.dumps(dates_list)
                state_record.state = 'awaiting_deadline'
                db.session.commit()
                
                poll_name = "⏱️ Wähle die Abstimmungs-Deadline:"
                options = ["⏱️ In 12 Stunden", "⏱️ In 24 Stunden", "⏱️ In 48 Stunden", "⏱️ In 3 Tagen"]
                resp = wa_client.send_poll(chat_id, poll_name, options, multiple_answers=False)
                if resp and resp.get('id'):
                    state_record.whatsapp_poll_id = normalize_id(resp.get('id'))
                    db.session.commit()
                else:
                    wa_client.send_message(chat_id, "❌ Fehler beim Senden der Deadline-Umfrage. Bitte versuche es erneut.")
                return jsonify({"status": "success"}), 200
                
    elif event == 'poll.vote':
        payload = data.get('payload', {})
        
        # Robustly extract poll message ID
        poll_message_id = (
            payload.get('pollMessageId') or 
            payload.get('poll', {}).get('id') or 
            payload.get('vote', {}).get('pollId') or 
            payload.get('vote', {}).get('id') or 
            payload.get('pollId')
        )
        
        sender = (
            payload.get('sender') or 
            payload.get('vote', {}).get('sender') or 
            payload.get('vote', {}).get('from') or 
            payload.get('from')
        )
        
        raw_options = (
            payload.get('selectedOptions') or 
            payload.get('vote', {}).get('selectedOptions') or 
            []
        )
        
        selected_options = []
        for opt in raw_options:
            if isinstance(opt, dict):
                val = opt.get('name') or opt.get('text') or opt.get('value') or ""
                if val:
                    selected_options.append(str(val).strip())
            elif opt is not None:
                selected_options.append(str(opt).strip())
                
        if poll_message_id and sender:
            # Check if this is a config vote for a WhatsAppState setup flow
            state_record = WhatsAppState.query.filter_by(whatsapp_poll_id=poll_message_id).first()
            if state_record:
                if not selected_options:
                    return jsonify({"status": "ignored"}), 200
                    
                selected_option = selected_options[0]
                
                if state_record.state == 'awaiting_type':
                    if "Liga" in selected_option:
                        state_record.poll_type = 'liga'
                        prompt = "Du hast *🏆 Liga Spiel* ausgewählt.\n\nBitte antworte jetzt mit dem *Titel* der Abstimmung (z.B. `DS vs. GegnerName`):"
                    else:
                        state_record.poll_type = 'single'
                        prompt = "Du hast *⚔️ TCW / Single Event* ausgewählt.\n\nBitte antworte jetzt mit dem *Titel* der Abstimmung (z.B. `TCW Woche 5`):"
                    
                    state_record.state = 'awaiting_title'
                    state_record.whatsapp_poll_id = None
                    db.session.commit()
                    
                    wa_client.send_message(state_record.chat_id, prompt)
                    return jsonify({"status": "success"}), 200
                    
                elif state_record.state == 'awaiting_deadline':
                    now = datetime.now()
                    if "12" in selected_option:
                        deadline = now + timedelta(hours=12)
                    elif "24" in selected_option:
                        deadline = now + timedelta(hours=24)
                    elif "48" in selected_option:
                        deadline = now + timedelta(hours=48)
                    else:
                        deadline = now + timedelta(days=3)
                    
                    poll_type = state_record.poll_type
                    title = state_record.title
                    
                    try:
                        parsed_dates = json.loads(state_record.dates)
                    except Exception:
                        parsed_dates = []
                        
                    new_poll = Poll(
                        title=title,
                        description="Erstellt per WhatsApp",
                        deadline=deadline,
                        poll_type=poll_type,
                        whatsapp_creator_chat_id=state_record.chat_id
                    )
                    db.session.add(new_poll)
                    db.session.flush()
                    
                    options_list = []
                    for s_dt_str, e_dt_str in parsed_dates:
                        s_dt = datetime.strptime(s_dt_str, '%Y-%m-%d %H:%M:%S')
                        e_dt = datetime.strptime(e_dt_str, '%Y-%m-%d %H:%M:%S')
                        new_opt = Option(poll_id=new_poll.id, start_time=s_dt, end_time=e_dt)
                        db.session.add(new_opt)
                        options_list.append(new_opt)
                    
                    db.session.commit()
                    
                    # Sende die Umfrage an die Gruppe (Standardgruppe des Admins)
                    admin_user = User.query.filter_by(whatsapp_admin_chat_id=state_record.chat_id, is_admin=True).first()
                    target_chat_id = (admin_user.whatsapp_chat_id if admin_user else None) or state_record.chat_id
                    
                    wa_options = [format_option_for_whatsapp(opt) for opt in options_list]
                    poll_name = f"⚔️ Abstimmung: {new_poll.title}"
                    
                    response = wa_client.send_poll(target_chat_id, poll_name, wa_options, multiple_answers=True)
                    if response and response.get('id'):
                        new_poll.whatsapp_poll_id = normalize_id(response.get('id'))
                        db.session.commit()
                        
                        success_msg = f"✅ *Abstimmung erfolgreich gestartet!*\n\nDie Umfrage wurde in die Gruppe gesendet."
                        wa_client.send_message(state_record.chat_id, success_msg)
                    else:
                        error_msg = f"❌ *Fehler beim Starten der Umfrage auf WhatsApp.*\nDie Abstimmung wurde in der App erstellt, konnte aber nicht an WhatsApp gesendet werden."
                        wa_client.send_message(state_record.chat_id, error_msg)
                        
                    db.session.delete(state_record)
                    db.session.commit()
                    
                    return jsonify({"status": "success"}), 200
            
            else:
                # Normal voter vote processing
                success = process_whatsapp_vote(poll_message_id, sender, selected_options)
                if success:
                    return jsonify({"status": "success"}), 200
                else:
                    return jsonify({"status": "error", "message": "Poll not found"}), 404
                    
    return jsonify({"status": "ignored"}), 200


