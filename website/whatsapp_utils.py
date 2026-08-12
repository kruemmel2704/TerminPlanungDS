import os
import requests
from whatsapp_api_client_python import API

def normalize_id(id_val):
    if not id_val:
        return ""
    if isinstance(id_val, dict):
        return id_val.get('_serialized') or id_val.get('id') or f"{id_val.get('user')}@{id_val.get('server')}"
    return str(id_val)


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
            "name": "default",
            "config": {
                "store": {
                    "enabled": True,
                    "fullSync": True
                }
            }
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
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key

        # 1. Try to fetch from /api/default/chats
        url_chats = f"{self.api_url.rstrip('/')}/api/default/chats"
        try:
            response = requests.get(url_chats, headers=headers, timeout=10)
            if response.status_code == 200:
                chats_data = response.json()
                if isinstance(chats_data, list) and len(chats_data) > 0:
                    chats = []
                    for chat in chats_data:
                        chat_id = normalize_id(chat.get('id'))
                        raw_name = chat.get('name') or chat.get('subject')
                        name = raw_name if raw_name else chat_id
                        prefix = "👥 " if chat_id.endswith('@g.us') else "👤 "
                        chats.append({
                            'id': chat_id,
                            'groupName': f"{prefix}{name}"
                        })
                    return chats
        except Exception as e:
            print(f"Error getting from /api/default/chats: {e}")

        # 2. Fallback: try to fetch from /api/default/chats/overview
        url_overview = f"{self.api_url.rstrip('/')}/api/default/chats/overview"
        try:
            response = requests.get(url_overview, headers=headers, timeout=10)
            if response.status_code == 200:
                chats_data = response.json()
                if isinstance(chats_data, list) and len(chats_data) > 0:
                    chats = []
                    for chat in chats_data:
                        chat_id = normalize_id(chat.get('id'))
                        raw_name = chat.get('name')
                        name = raw_name if raw_name else chat_id
                        prefix = "👥 " if chat_id.endswith('@g.us') else "👤 "
                        chats.append({
                            'id': chat_id,
                            'groupName': f"{prefix}{name}"
                        })
                    return chats
        except Exception as e:
            print(f"Error getting from /api/default/chats/overview: {e}")

        # 3. Fallback: try to fetch specifically from /api/default/groups
        url_groups = f"{self.api_url.rstrip('/')}/api/default/groups"
        try:
            response = requests.get(url_groups, headers=headers, timeout=10)
            if response.status_code == 200:
                groups_data = response.json()
                if isinstance(groups_data, list) and len(groups_data) > 0:
                    groups = []
                    for g in groups_data:
                        g_id = normalize_id(g.get('id'))
                        raw_name = g.get('name') or g.get('subject')
                        g_name = raw_name if raw_name else g_id
                        groups.append({
                            'id': g_id,
                            'groupName': f"👥 {g_name}"
                        })
                    return groups
        except Exception as e:
            print(f"Error getting from /api/default/groups: {e}")

        return []

    def send_message(self, chat_id, text, reply_to=None):
        url = f"{self.api_url.rstrip('/')}/api/sendText"
        payload = {
            "session": "default",
            "chatId": chat_id,
            "text": text
        }
        if reply_to:
            payload["reply_to"] = reply_to
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
            if response.status_code in [200, 201]:
                return response.json()
            return None
        except Exception as e:
            print(f"Error sending poll: {e}")
            return None

    def get_contact(self, contact_id):
        url = f"{self.api_url.rstrip('/')}/api/contacts"
        params = {
            "session": "default",
            "contactId": contact_id
        }
        headers = {}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            response = requests.get(url, params=params, headers=headers, timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting contact: {e}")
        return None

    def send_image_base64(self, chat_id, mimetype, filename, base64_data, caption=None):
        url = f"{self.api_url.rstrip('/')}/api/sendImage"
        payload = {
            "session": "default",
            "chatId": chat_id,
            "file": {
                "mimetype": mimetype,
                "filename": filename,
                "data": base64_data
            }
        }
        if caption:
            payload["caption"] = caption
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"Error sending image base64: {e}")
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

