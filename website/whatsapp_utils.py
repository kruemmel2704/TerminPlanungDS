import os
import requests
from whatsapp_api_client_python import API

class WhatsAppClient:
    def __init__(self):
        self.api_url = os.getenv('WHATSAPP_API_URL', 'http://waha:3000')
        self.api_key = os.getenv('WHATSAPP_API_KEY')

    def is_configured(self):
        return bool(self.api_url)

    def start_session(self):
        url = f"{self.api_url.rstrip('/')}/api/sessions/default/start"
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            requests.post(url, headers=headers, timeout=5)
        except Exception:
            pass

    def create_session(self):
        url = f"{self.api_url.rstrip('/')}/api/sessions"
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        payload = {
            "name": "default"
        }
        try:
            requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception:
            pass

    def get_status(self):
        url = f"{self.api_url.rstrip('/')}/api/sessions/default"
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                
                # Map WAHA states to Green-API expected states (online, authorized, notAuthorized, unconfigured)
                if status == 'WORKING':
                    return {'stateInstance': 'online'}
                elif status in ['SCAN_QR_CODE', 'STARTING']:
                    return {'stateInstance': 'notAuthorized'}
                elif status == 'STOPPED':
                    self.start_session()
                    return {'stateInstance': 'notAuthorized'}
                else:
                    return {'stateInstance': status}
            elif response.status_code == 404:
                self.create_session()
                return {'stateInstance': 'notAuthorized'}
            return {'stateInstance': 'error', 'message': f"Status code {response.status_code}"}
        except Exception as e:
            return {'stateInstance': 'error', 'message': str(e)}

    def get_qr_code(self):
        url = f"{self.api_url.rstrip('/')}/api/default/auth/qr?format=image"
        headers = {
            "Accept": "application/json"
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {"message": data.get('data')}
            return None
        except Exception:
            return None

    def logout(self):
        url = f"{self.api_url.rstrip('/')}/api/sessions/default/logout"
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            response = requests.post(url, headers=headers, timeout=10)
            return response.status_code in [200, 201]
        except Exception:
            return False

    def get_groups(self):
        url = f"{self.api_url.rstrip('/')}/api/default/chats"
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                chats = response.json()
                groups = []
                for chat in chats:
                    chat_id = chat.get('id')
                    is_group = chat_id.endswith('@g.us')
                    name = chat.get('name') or chat_id
                    groups.append({
                        'id': chat_id,
                        'groupName': f"👥 {name}" if is_group else f"👤 {name}"
                    })
                return groups
            return []
        except Exception as e:
            print(f"Error getting chats: {e}")
            return []

    def send_message(self, chat_id, text):
        url = f"{self.api_url.rstrip('/')}/api/sendText"
        payload = {
            "session": "default",
            "chatId": chat_id,
            "text": text
        }
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    def send_poll(self, chat_id, poll_name, options, multiple_answers=False):
        url = f"{self.api_url.rstrip('/')}/api/sendPoll"
        payload = {
            "session": "default",
            "chatId": chat_id,
            "poll": {
                "name": poll_name,
                "options": options,
                "multipleAnswers": multiple_answers
            }
        }
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"Error sending poll: {e}")
            return False


def send_whatsapp_notification(text):
    api_url = os.getenv('WHATSAPP_API_URL', 'http://waha:3000')
    chat_id = os.getenv('WHATSAPP_GROUP_JID')
    api_key = os.getenv('WHATSAPP_API_KEY')
    
    if not chat_id:
        print("WAHA Warning: WHATSAPP_GROUP_JID is not configured. Notification not sent.")
        return False
        
    url = f"{api_url.rstrip('/')}/api/sendText"
    payload = {
        "session": "default",
        "chatId": chat_id,
        "text": text
    }
    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["X-Api-Key"] = api_key
        
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            print("WAHA Success: WhatsApp notification sent successfully!")
            return True
        else:
            print(f"WAHA Error: Failed to send WhatsApp notification. Status code: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"WAHA Exception: Failed to connect to WhatsApp API: {e}")
        return False

