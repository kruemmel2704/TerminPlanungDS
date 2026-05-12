from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .whatsapp_utils import WhatsAppClient
from .models import Poll, Option
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
        flash('Green-API ist noch nicht in der .env konfiguriert!', category='warning')
        return render_template("whatsapp.html", status="unconfigured", user=current_user)

    state_resp = wa_client.get_status()
    state = state_resp.get('stateInstance')
    
    qr_data = None
    if state == 'notAuthorized':
        qr_resp = wa_client.get_qr_code()
        if qr_resp:
            qr_data = qr_resp.get('message')

    return render_template("whatsapp.html", 
                           status=state, 
                           qr_data=qr_data, 
                           user=current_user)

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
    
    if request.method == 'POST':
        chat_id = request.form.get('chat_id')
        if not chat_id:
            flash('Bitte wähle eine Gruppe aus!', category='error')
        else:
            options = [opt.start_time.strftime("%d.%m. %H:%M") for opt in poll.options]
            poll_name = f"Abstimmung: {poll.title}"
            if poll.description:
                poll_name += f"\n{poll.description}"
            
            if wa_client.send_poll(chat_id, poll_name, options):
                flash(f'Umfrage wurde erfolgreich an WhatsApp gesendet!', category='success')
                return redirect(url_for('routes.admin_dashboard'))
            else:
                flash('Fehler beim Senden der Umfrage.', category='error')

    groups = wa_client.get_groups()
    return render_template("whatsapp_share.html", poll=poll, groups=groups, user=current_user)
