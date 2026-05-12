import os
from whatsapp_api_client_python import API

class WhatsAppClient:
    def __init__(self):
        self.id_instance = os.getenv('GREEN_API_ID')
        self.api_token = os.getenv('GREEN_API_TOKEN')
        
        if self.id_instance and self.api_token:
            self.api = API.GreenApi(self.id_instance, self.api_token)
        else:
            self.api = None

    def is_configured(self):
        return self.api is not None

    def get_status(self):
        if not self.api:
            return {"status": "unconfigured"}
        try:
            response = self.api.account.getStateInstance()
            if response.code == 200:
                return response.data
            return {"status": "error", "message": f"Code {response.code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_qr_code(self):
        if not self.api:
            return None
        try:
            response = self.api.account.qr()
            if response.code == 200:
                return response.data # Contains 'message' which is the base64 or similar
            return None
        except Exception:
            return None

    def logout(self):
        if not self.api:
            return False
        try:
            response = self.api.account.logout()
            return response.code == 200
        except Exception:
            return False

    def get_groups(self):
        if not self.api:
            return []
        try:
            # Use getContacts as it is more reliable in recent versions
            response = self.api.serviceMethods.getContacts()
            if response.code == 200 and isinstance(response.data, list):
                # Filter for groups (chatId ends with @g.us or type is 'group')
                groups = []
                for contact in response.data:
                    is_group = contact.get('type') == 'group' or (contact.get('id') and contact.get('id').endswith('@g.us'))
                    if is_group:
                        # Normalize field names for the template
                        group_name = contact.get('name') or contact.get('groupName') or contact.get('id')
                        groups.append({
                            'id': contact.get('id'),
                            'groupName': group_name
                        })
                return groups
                
            return []
        except Exception as e:
            print(f"Error getting groups: {e}")
            return []

    def send_poll(self, chat_id, poll_name, options, multiple_answers=False):
        if not self.api:
            return False
        try:
            # options must be a list of objects like [{"optionName": "Option 1"}, ...]
            formatted_options = [{"optionName": opt} for opt in options]
            
            # Use positional arguments: chatId, message (pollName), options
            # The SDK expects: sendPoll(chatId, message, options, multipleAnswers)
            response = self.api.sending.sendPoll(
                chat_id,
                poll_name,
                formatted_options,
                multipleAnswers=multiple_answers
            )
            return response.code == 200
        except Exception as e:
            print(f"Error sending poll: {e}")
            return False
