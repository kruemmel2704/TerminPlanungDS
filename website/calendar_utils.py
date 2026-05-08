import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .models import Poll, Option
from . import db

def get_calendar_service(user):
    if not user.google_token:
        return None
    
    token_data = json.loads(user.google_token)
    credentials = Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data['token_uri'],
        client_id=token_data['client_id'],
        client_secret=token_data['client_secret'],
        scopes=token_data['scopes']
    )
    
    return build('calendar', 'v3', credentials=credentials)

def create_league_calendar(user):
    service = get_calendar_service(user)
    if not service:
        return None
    
    calendar = {
        'summary': 'Liga Spielplan (Allgemein)',
        'timeZone': 'Europe/Berlin'
    }
    
    created_calendar = service.calendars().insert(body=calendar).execute()
    
    # Make calendar public
    rule = {
        'scope': {'type': 'default'},
        'role': 'reader'
    }
    service.acl().insert(calendarId=created_calendar['id'], body=rule).execute()
    
    return created_calendar['id']

def add_event_to_calendar(user, option, title, description=""):
    service = get_calendar_service(user)
    if not service or not user.google_calendar_id:
        return False
    
    event = {
        'summary': f'Spiel: {title}',
        'description': description if description else 'Automatisch erstellt durch Liga Planer',
        'start': {
            'dateTime': option.start_time.isoformat(),
            'timeZone': 'Europe/Berlin',
        },
        'end': {
            'dateTime': option.end_time.isoformat(),
            'timeZone': 'Europe/Berlin',
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 24 * 60},  # 1 Tag vorher
                {'method': 'popup', 'minutes': 60},       # 1 Stunde vorher
            ],
        },
    }
    
    service.events().insert(calendarId=user.google_calendar_id, body=event).execute()
    return True
