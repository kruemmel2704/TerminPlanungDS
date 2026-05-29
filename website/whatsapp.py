from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .whatsapp_utils import WhatsAppClient, normalize_id
from .models import Poll, Option, Vote, User, WhatsAppState, WhatsAppSearch
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
            
            if wa_client.send_message(chat_id, message, reply_to=poll.whatsapp_poll_id):
                flash(f'Reminder wurde erfolgreich an WhatsApp gesendet!', category='success')
                return redirect(url_for('routes.admin_dashboard'))
            else:
                flash('Fehler beim Senden des Reminders.', category='error')

    groups = wa_client.get_groups()
    return render_template("whatsapp_share.html", poll=poll, groups=groups, user=current_user)

def get_sticker_base64():
    import base64
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sticker_path = os.path.join(base_dir, 'static', 'images', 'tcw_sticker.png')
    try:
        if os.path.exists(sticker_path):
            with open(sticker_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        else:
            print(f"Sticker file not found at: {sticker_path}")
            return None
    except Exception as e:
        print(f"Error reading sticker file: {e}")
        return None

def send_search_post_now(groups_list):
    sticker_base64 = get_sticker_base64()
    for group_id in groups_list:
        if sticker_base64:
            wa_client.send_image_base64(
                chat_id=group_id,
                mimetype="image/png",
                filename="tcw_sticker.png",
                base64_data=sticker_base64
            )
        wa_client.send_message(group_id, "wir suchen heute abend ein TCW um 20:30")

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
    
    if poll.poll_type == 'single' and len(options) == 1:
        if "Ja" in selected_options:
            opt = options[0]
            new_vote = Vote(
                option_id=opt.id,
                user_id=system_user.id,
                user_name=display_name,
                whatsapp_sender=sender_jid,
                is_whatsapp=True
            )
            db.session.add(new_vote)
    else:
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
            if poll.poll_type == 'single' and len(poll.options) == 1:
                opt = poll.options[0]
                formatted_date = format_option_for_whatsapp(opt)
                options_list = ["Ja", "Nein"]
                poll_name = f"⚔️ Abstimmung: {poll.title}\nDatum: {formatted_date}"
                if poll.description:
                    poll_name += f"\n{poll.description}"
                response = wa_client.send_poll(chat_id, poll_name, options_list, multiple_answers=False)
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
        if payload.get('fromMe'):
            return jsonify({"status": "ignored"}), 200
            
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
            
        elif body.lower() == '/clansitzung':
            if not admin_user:
                wa_client.send_message(chat_id, "❌ Dieser Chat ist nicht als Admin-Chat autorisiert. Bitte konfiguriere ihn in den Einstellungen unter /whatsapp.")
                return jsonify({"status": "unauthorized"}), 200
                
            # Clear any existing state for this chat
            WhatsAppState.query.filter_by(chat_id=chat_id).delete()
            db.session.commit()
            
            # Start flow directly at awaiting_title with poll_type='clansitzung'
            new_state = WhatsAppState(
                chat_id=chat_id,
                sender_jid=sender_jid,
                state='awaiting_title',
                poll_type='clansitzung'
            )
            db.session.add(new_state)
            db.session.commit()
            
            prompt = "Du hast eine *Clansitzung (7 Tage Abfrage)* gestartet.\n\nBitte antworte jetzt mit dem *Titel* der Clansitzung (z.B. `Clansitzung Juni`):"
            wa_client.send_message(chat_id, prompt)
            return jsonify({"status": "success"}), 200
            
        elif body.lower() == '/zwischenstand':
            if not admin_user:
                wa_client.send_message(chat_id, "❌ Dieser Chat ist nicht als Admin-Chat autorisiert. Bitte konfiguriere ihn in den Einstellungen unter /whatsapp.")
                return jsonify({"status": "unauthorized"}), 200
                
            # Clear any existing state for this chat
            WhatsAppState.query.filter_by(chat_id=chat_id).delete()
            db.session.commit()
            
            active_polls = Poll.query.filter_by(is_active=True).all()
            if not active_polls:
                wa_client.send_message(chat_id, "❌ Aktuell gibt es keine aktiven Abstimmungen.")
                return jsonify({"status": "no_active_polls"}), 200
                
            # Start flow
            new_state = WhatsAppState(
                chat_id=chat_id,
                sender_jid=sender_jid,
                state='awaiting_zwischenstand_poll'
            )
            db.session.add(new_state)
            db.session.commit()
            
            poll_name = "📊 Wähle die Abstimmung für den Zwischenstand:"
            options = []
            for p in active_polls:
                opt_text = f"[{p.id}] {p.title}"
                if len(opt_text) > 80:
                    opt_text = opt_text[:77] + "..."
                options.append(opt_text)
                
            resp = wa_client.send_poll(chat_id, poll_name, options, multiple_answers=False)
            if resp and resp.get('id'):
                new_state.whatsapp_poll_id = normalize_id(resp.get('id'))
                db.session.commit()
            else:
                wa_client.send_message(chat_id, "❌ Fehler beim Senden der Abstimmungs-Auswahl. Bitte versuche es erneut.")
            return jsonify({"status": "success"}), 200

        elif body.lower() in ['/statics', '/statistik', '/statistics']:
            if not admin_user:
                wa_client.send_message(chat_id, "❌ Dieser Chat ist nicht als Admin-Chat autorisiert. Bitte konfiguriere ihn in den Einstellungen unter /whatsapp.")
                return jsonify({"status": "unauthorized"}), 200
                
            votes = Vote.query.all()
            polls = Poll.query.all()
            polls_count = len(polls)
            
            if not votes or polls_count == 0:
                wa_client.send_message(chat_id, "ℹ️ Es liegen noch keine Abstimmungen oder Stimmen vor, um Statistiken anzuzeigen.")
                return jsonify({"status": "no_data"}), 200
                
            voter_polls = {}
            voter_names = {}
            voter_total_votes = {}
            
            for vote in votes:
                option = Option.query.get(vote.option_id)
                if not option:
                    continue
                poll_id = option.poll_id
                
                if vote.is_whatsapp:
                    voter_id = vote.whatsapp_sender
                else:
                    voter_id = f"web_{vote.user_id}"
                    
                if voter_id not in voter_polls:
                    voter_polls[voter_id] = set()
                voter_polls[voter_id].add(poll_id)
                
                voter_names[voter_id] = vote.user_name
                voter_total_votes[voter_id] = voter_total_votes.get(voter_id, 0) + 1
                
            # Sort by participation count (descending)
            sorted_voters = sorted(voter_polls.items(), key=lambda x: len(x[1]), reverse=True)
            
            msg = "📊 *Statistik: Wer stimmt am fleißigsten ab?*\n\n"
            for voter_id, voted_polls in sorted_voters:
                name = voter_names[voter_id]
                count = len(voted_polls)
                pct = (count / polls_count) * 100
                
                avg_choices = voter_total_votes[voter_id] / count if count > 0 else 0
                
                msg += f"• *{name}*:\n"
                msg += f"  Teilnahme: {pct:.1f}% ({count}/{polls_count} Umfragen)\n"
                msg += f"  Stimmen pro Umfrage: {avg_choices:.1f}\n\n"
                
            wa_client.send_message(chat_id, msg)
            return jsonify({"status": "success"}), 200

        elif body.lower() == '/suche-starten':
            if not admin_user:
                wa_client.send_message(chat_id, "❌ Dieser Chat ist nicht als Admin-Chat autorisiert. Bitte konfiguriere ihn in den Einstellungen unter /whatsapp.")
                return jsonify({"status": "unauthorized"}), 200

            # Clear any existing state for this chat
            WhatsAppState.query.filter_by(chat_id=chat_id).delete()
            db.session.commit()

            groups = wa_client.get_groups()
            groups = [g for g in groups if g['id'].endswith('@g.us')]

            if not groups:
                wa_client.send_message(chat_id, "❌ Keine WhatsApp-Gruppen für die Suche gefunden.")
                return jsonify({"status": "no_groups"}), 200

            # Limit groups to 11 to fit within the WhatsApp poll maximum options (12 options total)
            groups = groups[:11]

            options = []
            group_mapping = []
            for idx, g in enumerate(groups, 1):
                name = g['groupName']
                options.append(f"[{idx}] {name}")
                group_mapping.append({"index": idx, "id": g['id'], "name": name})

            options.append("👉 [START] Suche starten")

            new_state = WhatsAppState(
                chat_id=chat_id,
                sender_jid=sender_jid,
                state='awaiting_search_groups',
                dates=json.dumps(group_mapping)
            )
            db.session.add(new_state)
            db.session.commit()

            poll_name = "🔍 Wähle die Gruppen für die TCW-Suche aus (Mehrfachauswahl möglich, danach 'Suche starten' wählen):"
            resp = wa_client.send_poll(chat_id, poll_name, options, multiple_answers=True)
            if resp and resp.get('id'):
                new_state.whatsapp_poll_id = normalize_id(resp.get('id'))
                db.session.commit()
            else:
                wa_client.send_message(chat_id, "❌ Fehler beim Senden der Gruppen-Auswahl. Bitte versuche es erneut.")
            return jsonify({"status": "success"}), 200

        elif body.lower() == '/suche-stoppen':
            if not admin_user:
                wa_client.send_message(chat_id, "❌ Dieser Chat ist nicht als Admin-Chat autorisiert. Bitte konfiguriere ihn in den Einstellungen unter /whatsapp.")
                return jsonify({"status": "unauthorized"}), 200

            search = WhatsAppSearch.query.first()
            if not search or not search.is_active:
                wa_client.send_message(chat_id, "ℹ️ Es läuft aktuell keine aktive Suche.")
                return jsonify({"status": "no_active_search"}), 200

            search.is_active = False
            db.session.commit()

            wa_client.send_message(chat_id, "Tut uns leid wir haben schon ein Match gefunden.")
            wa_client.send_message(chat_id, "⏹️ *Suche wurde beendet.*")
            return jsonify({"status": "success"}), 200

        # Check if it is a user DM (ends with @c.us) and matches keywords
        if chat_id.endswith('@c.us'):
            body_lower = body.lower()
            is_query = any(phrase in body_lower for phrase in ["sucht ihr", "suchen noch", "tcw?", "cw?", "sucht ihr tcw", "sucht ihr cw", "spielmöglichkeit", "suchen noch tcw", "habt ihr noch tcw"])
            if is_query:
                search = WhatsAppSearch.query.first()
                if search and search.is_active:
                    wa_client.send_message(chat_id, "Ja ein Teammitglied wird sich bald melden für weitere details.")
                    
                    # Notify admin chat
                    admin_users = User.query.filter(User.whatsapp_admin_chat_id != None, User.is_admin == True).all()
                    for admin in admin_users:
                        contact_name = None
                        contact_data = wa_client.get_contact(sender_jid)
                        if contact_data:
                            contact_name = contact_data.get('name') or contact_data.get('pushname') or contact_data.get('shortName')
                        
                        phone = sender_jid.split('@')[0]
                        display_name = f"{contact_name} (+{phone})" if contact_name else f"+{phone}"
                        
                        admin_msg = f"🔔 *Es wurde eine Spielmöglichkeit gefunden!*\n\nAnfrage von: {display_name}\nNachricht: \"{body}\""
                        wa_client.send_message(admin.whatsapp_admin_chat_id, admin_msg)
                else:
                    wa_client.send_message(chat_id, "Tut uns leid wir haben schon ein Match gefunden.")
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
                elif state_record.poll_type == 'clansitzung':
                    prompt = (
                        f"Titel: *{body}*\n\n"
                        "Bitte gib das *Startdatum* für die Clansitzung an (Format: `TT.MM.JJJJ`, z.B. `26.05.2026`).\n"
                        "Der Bot generiert automatisch 7 Termine an aufeinanderfolgenden Tagen ab diesem Datum (jeweils um 20:30 Uhr)."
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
                
                if state_record.poll_type in ['liga', 'clansitzung']:
                    base_date = parse_german_date(body)
                    if not base_date:
                        wa_client.send_message(chat_id, "❌ *Ungültiges Datum.* Bitte verwende das Format `TT.MM.JJJJ` (z.B. `26.05.2026`):")
                        return jsonify({"status": "invalid_date"}), 200
                    
                    num_days = 7 if state_record.poll_type == 'clansitzung' else 5
                    for i in range(num_days):
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

                if state_record.state == 'awaiting_search_groups':
                    has_start = any("Suche starten" in opt for opt in selected_options)
                    if not has_start:
                        return jsonify({"status": "waiting_for_start"}), 200

                    # Extract selected indices
                    import re
                    selected_indices = []
                    for opt in selected_options:
                        match = re.match(r'^\[(\d+)\]', opt)
                        if match:
                            selected_indices.append(int(match.group(1)))

                    if not selected_indices:
                        wa_client.send_message(state_record.chat_id, "❌ Bitte wähle mindestens eine Gruppe aus, bevor du die Suche startest.")
                        return jsonify({"status": "no_groups_selected"}), 200

                    try:
                        group_mapping = json.loads(state_record.dates)
                    except Exception:
                        group_mapping = []

                    selected_group_ids = []
                    selected_group_names = []
                    for mapping in group_mapping:
                        if mapping["index"] in selected_indices:
                            selected_group_ids.append(mapping["id"])
                            selected_group_names.append(mapping["name"])

                    if not selected_group_ids:
                        wa_client.send_message(state_record.chat_id, "❌ Keine gültigen Gruppen ausgewählt.")
                        return jsonify({"status": "invalid_groups"}), 200

                    # Start/update search state
                    search = WhatsAppSearch.query.first()
                    if not search:
                        search = WhatsAppSearch()
                        db.session.add(search)

                    search.is_active = True
                    search.groups = json.dumps(selected_group_ids)
                    search.last_sent_at = datetime.utcnow()
                    db.session.commit()

                    # Delete State Record
                    db.session.delete(state_record)
                    db.session.commit()

                    # Notify Admin
                    groups_str = ", ".join(selected_group_names)
                    wa_client.send_message(state_record.chat_id, f"✅ *Suche wurde gestartet!*\n\nGruppen:\n{groups_str}\n\nDer Bot postet nun stündlich die Suchanfrage in diese Gruppen.")

                    # Trigger post immediately
                    send_search_post_now(selected_group_ids)
                    return jsonify({"status": "success"}), 200

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
                    
                elif state_record.state == 'awaiting_zwischenstand_poll':
                    import re
                    match = re.match(r'^\[(\d+)\]', selected_option)
                    if not match:
                        wa_client.send_message(state_record.chat_id, "❌ Ungültige Auswahl. Bitte wähle eine Option aus der Liste.")
                        db.session.delete(state_record)
                        db.session.commit()
                        return jsonify({"status": "invalid_selection"}), 200
                        
                    poll_id = int(match.group(1))
                    poll = Poll.query.get(poll_id)
                    if not poll:
                        wa_client.send_message(state_record.chat_id, "❌ Abstimmung nicht gefunden.")
                        db.session.delete(state_record)
                        db.session.commit()
                        return jsonify({"status": "poll_not_found"}), 200
                        
                    msg = f"📊 *Zwischenstand: {poll.title}*\n\n"
                    msg += "Aktuelle Stimmen:\n"
                    
                    sorted_opts = []
                    for opt in poll.options:
                        sorted_opts.append((opt, len(opt.votes)))
                    sorted_opts.sort(key=lambda x: (-x[1], x[0].start_time))
                    
                    for opt, count in sorted_opts:
                        opt_str = format_option_for_whatsapp(opt)
                        voters = ", ".join([v.user_name for v in opt.votes])
                        if voters:
                            msg += f"• {opt_str}: *{count} Stimme(n)* ({voters})\n"
                        else:
                            msg += f"• {opt_str}: *{count} Stimme(n)*\n"
                            
                    wa_client.send_message(state_record.chat_id, msg)
                    
                    admin_user = User.query.filter_by(whatsapp_admin_chat_id=state_record.chat_id, is_admin=True).first()
                    target_chat_id = (admin_user.whatsapp_chat_id if admin_user else None)
                    if target_chat_id and target_chat_id != state_record.chat_id:
                        wa_client.send_message(target_chat_id, msg)
                        wa_client.send_message(state_record.chat_id, "✅ Der Zwischenstand wurde auch in die Gruppe gesendet.")
                        
                    db.session.delete(state_record)
                    db.session.commit()
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
                    
                    if new_poll.poll_type == 'single' and len(options_list) == 1:
                        opt = options_list[0]
                        formatted_date = format_option_for_whatsapp(opt)
                        wa_options = ["Ja", "Nein"]
                        poll_name = f"⚔️ Abstimmung: {new_poll.title}\nDatum: {formatted_date}"
                        response = wa_client.send_poll(target_chat_id, poll_name, wa_options, multiple_answers=False)
                    else:
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


def start_reminder_scheduler(app):
    import threading
    import time
    from datetime import datetime, timezone, timedelta
    
    def scheduler_loop():
        # Wait a few seconds to let the application start up fully
        time.sleep(10)
        while True:
            try:
                tz_utc_plus_1 = timezone(timedelta(hours=1))
                now = datetime.now(tz_utc_plus_1)
                if now.hour == 15:
                    with app.app_context():
                        from .models import Poll, User
                        import os
                        
                        # Fetch all active polls with a WhatsApp poll ID
                        active_polls = Poll.query.filter(
                            Poll.is_active == True,
                            Poll.whatsapp_poll_id != None,
                            Poll.whatsapp_poll_id != ''
                        ).all()
                        
                        for poll in active_polls:
                            # Check if a reminder was already sent today (UTC+1 day)
                            if poll.whatsapp_last_reminder_at:
                                last_reminder_utc_plus_1 = poll.whatsapp_last_reminder_at.replace(tzinfo=timezone.utc).astimezone(tz_utc_plus_1)
                                if last_reminder_utc_plus_1.date() == now.date():
                                    continue
                            
                            # Construct reminder message
                            redirect_uri = os.getenv('DISCORD_REDIRECT_URI') or 'http://localhost:5000/callback/discord'
                            base_url = redirect_uri.split('/callback/discord')[0]
                            vote_url = f"{base_url.rstrip('/')}/vote/{poll.id}"
                            
                            message = f"🔔 *Reminder: Abstimmung für {poll.title}*\n\n"
                            if poll.description:
                                message += f"{poll.description}\n\n"
                            message += f"Du hast noch nicht abgestimmt? Hier klicken:\n{vote_url}"
                            
                            # Get target chat ID
                            target_chat_id = None
                            if poll.whatsapp_creator_chat_id:
                                admin_user = User.query.filter_by(whatsapp_admin_chat_id=poll.whatsapp_creator_chat_id, is_admin=True).first()
                                target_chat_id = (admin_user.whatsapp_chat_id if admin_user else None) or poll.whatsapp_creator_chat_id
                            else:
                                admin_user = User.query.filter_by(is_admin=True).first()
                                if admin_user:
                                    target_chat_id = admin_user.whatsapp_chat_id
                                    
                            if target_chat_id:
                                success = wa_client.send_message(target_chat_id, message, reply_to=poll.whatsapp_poll_id)
                                if success:
                                    poll.whatsapp_last_reminder_at = datetime.utcnow()
                                    db.session.commit()
                                    print(f"Sent daily reminder for poll {poll.id} as a reply to {poll.whatsapp_poll_id}")
                                else:
                                    print(f"Failed to send daily reminder for poll {poll.id}")
                
                # Check for active TCW searches
                with app.app_context():
                    search = WhatsAppSearch.query.first()
                    if search and search.is_active:
                        now_utc = datetime.utcnow()
                        should_send = False
                        if not search.last_sent_at:
                            should_send = True
                        else:
                            elapsed = now_utc - search.last_sent_at
                            if elapsed >= timedelta(hours=1):
                                should_send = True
                                
                        if should_send:
                            try:
                                groups_list = json.loads(search.groups)
                            except Exception:
                                groups_list = []
                                
                            if groups_list:
                                send_search_post_now(groups_list)
                                
                            search.last_sent_at = now_utc
                            db.session.commit()
                            print("Sent hourly search post to groups.")
                
                # Sleep 60 seconds to avoid repeating within the same hour
                time.sleep(60)
            except Exception as e:
                print(f"Error in WhatsApp reminder scheduler: {e}")
                time.sleep(30)
                
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()


