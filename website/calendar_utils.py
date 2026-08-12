import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.exceptions import RefreshError
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

def get_calendar_list(user):
    service = get_calendar_service(user)
    if not service:
        return []
    try:
        calendar_list = service.calendarList().list().execute()
        return calendar_list.get('items', [])
    except RefreshError:
        user.google_token = None
        user.google_calendar_id = None
        user.google_calendar_name = None
        db.session.commit()
        return []
    except Exception as e:
        print(f"Failed to fetch calendar list: {e}")
        return []

def create_league_calendar(user, summary='Liga Spielplan (Allgemein)', make_public=True):
    service = get_calendar_service(user)
    if not service:
        return None
    
    calendar = {
        'summary': summary,
        'timeZone': 'Europe/Berlin'
    }
    
    try:
        created_calendar = service.calendars().insert(body=calendar).execute()
        
        if make_public:
            # Make calendar public
            rule = {
                'scope': {'type': 'default'},
                'role': 'reader'
            }
            service.acl().insert(calendarId=created_calendar['id'], body=rule).execute()
        
        return created_calendar['id']
    except RefreshError:
        user.google_token = None
        user.google_calendar_id = None
        user.google_calendar_name = None
        db.session.commit()
        return None
    except Exception as e:
        print(f"Calendar creation failed: {e}")
        return None

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
    
    try:
        service.events().insert(calendarId=user.google_calendar_id, body=event).execute()
        return True
    except RefreshError:
        user.google_token = None
        user.google_calendar_id = None
        user.google_calendar_name = None
        db.session.commit()
        return False
    except Exception as e:
        print(f"Event addition failed: {e}")
        return False
