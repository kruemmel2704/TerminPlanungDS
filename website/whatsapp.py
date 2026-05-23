from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .whatsapp_utils import WhatsAppClient, normalize_id
from .models import Poll, Option, Vote, User
from . import db

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
        opt_str = format_option_for_whatsapp(opt)
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
    if event == 'poll.vote':
        payload = data.get('payload', {})
        poll_message_id = payload.get('pollMessageId')
        sender = payload.get('sender')
        selected_options = payload.get('selectedOptions', [])
        
        if poll_message_id and sender:
            success = process_whatsapp_vote(poll_message_id, sender, selected_options)
            if success:
                return jsonify({"status": "success"}), 200
            else:
                return jsonify({"status": "error", "message": "Poll not found"}), 404
                
    return jsonify({"status": "ignored"}), 200


