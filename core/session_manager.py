import os

class SessionManager:
    def __init__(self):
        self.api_id = int(os.environ.get("API_ID", "0"))
        self.api_hash = os.environ.get("API_HASH", "")
        self.session_dir = os.environ.get("SESSION_DIR", "")

    def get_session_path(self, phone: str) -> str:
        name = f"session_{phone.replace('+', '')}"
        return os.path.join(self.session_dir, f"{name}.session") if self.session_dir else f"{name}.session"
