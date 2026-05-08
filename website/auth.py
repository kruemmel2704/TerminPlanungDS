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
    
    return redirect(url_for('routes.home'))

@auth.route('/login-page')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('routes.home'))
    return render_template('login.html', user=current_user)

# --- GOOGLE CALENDAR AUTH ---
@auth.route('/admin/connect-google')
@login_required
def connect_google():
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))
    
    flow = get_google_flow()
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
    session['google_state'] = state
    session['google_code_verifier'] = flow.code_verifier
    return redirect(authorization_url)

@auth.route('/admin/google-callback')
@login_required
def google_callback():
    if not current_user.is_admin:
        return redirect(url_for('routes.home'))

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
    
    db.session.commit()
    flash('Google Kalender erfolgreich verknüpft!', category='success')
    return redirect(url_for('routes.admin_dashboard'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login_page'))
