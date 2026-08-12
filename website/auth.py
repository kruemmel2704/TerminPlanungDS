import os
import json
import requests
from flask import Blueprint, render_template, redirect, url_for, request, session, current_app, flash
from flask_login import login_user, logout_user, login_required, current_user
from google_auth_oauthlib.flow import Flow
from .models import User
from . import db

auth = Blueprint('auth', __name__)

# Discord Config
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI')
GUILD_ID = os.getenv('DISCORD_GUILD_ID')
ADMIN_ROLE_ID = os.getenv('DISCORD_ADMIN_ROLE_ID')
USER_ROLE_ID = os.getenv('DISCORD_USER_ROLE_ID')
API_BASE_URL = 'https://discord.com/api'

# Google Config
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

def get_google_flow():
    client_config = {
        "web": {
            "client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [url_for('auth.google_callback', _external=True)]
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"],
        redirect_uri=url_for('auth.google_callback', _external=True)
    )

# --- DISCORD AUTH ---
@auth.route('/login')
def login():
    scope = 'identify guilds.members.read'
    auth_url = f"{API_BASE_URL}/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={DISCORD_REDIRECT_URI}&response_type=code&scope={scope}"
    return redirect(auth_url)

@auth.route('/callback/discord')
def discord_callback():
    code = request.args.get('code')
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(f"{API_BASE_URL}/oauth2/token", data=data, headers=headers)
    
    if r.status_code != 200:
        flash('Discord Login fehlgeschlagen.', category='error')
        return redirect(url_for('auth.login_page'))
    
    token = r.json()
    access_token = token['access_token']

    # 1. Get User Identity
    headers = {'Authorization': f"Bearer {access_token}"}
    user_info = requests.get(f"{API_BASE_URL}/users/@me", headers=headers).json()
    
    # 2. Get Guild Member Status via BOT TOKEN (More reliable)
    BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    bot_headers = {'Authorization': f"Bot {BOT_TOKEN}"}
    
    member_r = requests.get(f"{API_BASE_URL}/guilds/{GUILD_ID}/members/{user_info['id']}", headers=bot_headers)
    
    if member_r.status_code != 200:
        flash('Du bist kein Mitglied des erforderlichen Discord-Servers oder der Bot kann dich nicht sehen!', category='error')
        return redirect(url_for('auth.login_page'))
    
    member_data = member_r.json()
    roles = member_data.get('roles', [])
    
    # Use Server Nickname if available, otherwise global username
    display_name = member_data.get('nick') or user_info.get('global_name') or user_info['username']

    # Role Checks
    is_admin = ADMIN_ROLE_ID in roles
    has_user_role = (not USER_ROLE_ID) or (USER_ROLE_ID in roles) or is_admin

    if not has_user_role:
        flash('Du hast nicht die erforderliche Rolle für diese App!', category='error')
        return redirect(url_for('auth.login_page'))

    discord_id = user_info['id']
    user = User.query.filter_by(discord_id=discord_id).first()
    if not user:
        user = User(discord_id=discord_id, username=display_name, avatar=user_info['avatar'], is_admin=is_admin)
        db.session.add(user)
    else:
        user.username = display_name
        user.avatar = user_info['avatar']
        user.is_admin = is_admin
    
    db.session.commit()
    login_user(user, remember=True)
    
    return redirect('/')

@auth.route('/login-page')
def login_page():
    if current_user.is_authenticated:
        return redirect('/')
    return redirect('/#/login')

# --- GOOGLE CALENDAR AUTH ---
@auth.route('/admin/connect-google')
@login_required
def connect_google():
    if not current_user.is_admin:
        return redirect('/')
    
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
    session['google_state'] = state
    session['google_code_verifier'] = flow.code_verifier
    return redirect(authorization_url)

@auth.route('/admin/google-callback')
@login_required
def google_callback():
    if not current_user.is_admin:
        return redirect('/')

    flow = get_google_flow()
    flow.code_verifier = session.get('google_code_verifier')
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    current_user.google_token = json.dumps({
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    })
    
    db.session.commit()    flash('Google Kalender erfolgreich verknüpft!', category='success')
    return redirect('/#/admin/select-calendar')

@auth.route('/api/google/calendars', methods=['GET'])
@login_required
def api_google_calendars():
    from flask import jsonify
    if not current_user.is_admin:
        return jsonify({'message': 'Kein Zugriff!'}), 403
    from .calendar_utils import get_calendar_list
    calendars = get_calendar_list(current_user)
    return jsonify(calendars)

@auth.route('/api/google/select-calendar', methods=['POST'])
@login_required
def api_select_calendar():
    from flask import jsonify
    if not current_user.is_admin:
        return jsonify({'message': 'Kein Zugriff!'}), 403
        
    data = request.json or {}
    option = data.get('calendar_option')
    make_public = data.get('make_public') == 'y'
    
    from .calendar_utils import create_league_calendar, get_calendar_service
    
    if option == 'create':
        name = data.get('new_calendar_name', 'Liga Spielplan (Allgemein)')
        cal_id = create_league_calendar(current_user, summary=name, make_public=make_public)
        if cal_id:
            current_user.google_calendar_id = cal_id
            current_user.google_calendar_name = name
            db.session.commit()
            return jsonify({'message': f'Neuer Kalender "{name}" wurde erfolgreich erstellt und verknüpft!'})
        return jsonify({'message': 'Fehler beim Erstellen des neuen Kalenders.'}), 500
        
    elif option == 'existing':
        cal_id = data.get('existing_calendar_id')
        if not cal_id:
            return jsonify({'message': 'Bitte wähle einen existierenden Kalender aus!'}), 400
            
        service = get_calendar_service(current_user)
        summary = "Google Kalender"
        if service:
            try:
                cal_meta = service.calendars().get(calendarId=cal_id).execute()
                summary = cal_meta.get('summary', 'Google Kalender')
                
                if make_public:
                    rule = {
                        'scope': {'type': 'default'},
                        'role': 'reader'
                    }
                    service.acl().insert(calendarId=cal_id, body=rule).execute()
            except Exception as e:
                print(f"Error fetching/updating existing calendar: {e}")
                
        current_user.google_calendar_id = cal_id
        current_user.google_calendar_name = summary
        db.session.commit()
        return jsonify({'message': f'Erfolgreich mit dem Kalender "{summary}" verknüpft!'})
        
    return jsonify({'message': 'Ungültige Option'}), 400

@auth.route('/api/google/disconnect', methods=['POST'])
@login_required
def api_disconnect_google():
    from flask import jsonify
    if not current_user.is_admin:
        return jsonify({'message': 'Kein Zugriff!'}), 403
    current_user.google_token = None
    current_user.google_calendar_id = None
    current_user.google_calendar_name = None
    db.session.commit()
    return jsonify({'message': 'Verbindung mit Google Kalender wurde getrennt.'})


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/#/login')

@auth.route('/api/auth/status')
def auth_status():
    from flask import jsonify
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': current_user.id,
                'discord_id': current_user.discord_id,
                'username': current_user.username,
                'avatar': current_user.avatar,
                'is_admin': current_user.is_admin,
                'whatsapp_chat_id': current_user.whatsapp_chat_id,
                'whatsapp_chat_name': current_user.whatsapp_chat_name,
                'whatsapp_admin_chat_id': current_user.whatsapp_admin_chat_id,
                'whatsapp_admin_chat_name': current_user.whatsapp_admin_chat_name,
                'google_calendar_id': current_user.google_calendar_id,
                'google_token': current_user.google_token
            }
        })
    return jsonify({'authenticated': False})

@auth.route('/api/auth/logout')
@login_required
def api_logout():
    from flask import jsonify
    logout_user()
    return jsonify({'success': True})
