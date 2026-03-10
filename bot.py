import os
import asyncio
import re
import base64
from pyrogram import Client, filters, idle
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import aiohttp
from aiohttp import web

# --- Configuration ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# API Config
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@mailbot.techbittu.in")
EMAIL_API_KEY = os.environ.get("EMAIL_API_KEY") 

app = Client("premium_mailer_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# State management dictionary
users_data = {}

# --- Keyboards ---
file_choice_kb = ReplyKeyboardMarkup(
    [[KeyboardButton("Yes"), KeyboardButton("No")]], 
    resize_keyboard=True, placeholder="Attach a file?"
)

more_files_kb = ReplyKeyboardMarkup(
    [[KeyboardButton("Yes"), KeyboardButton("Continue")]], 
    resize_keyboard=True, placeholder="Attach another?"
)

# --- Helper Functions ---
def reset_user(user_id):
    if user_id in users_data:
        # Clean up local files to save Render disk space
        for file in users_data[user_id].get('files', []):
            if os.path.exists(file):
                os.remove(file)
        del users_data[user_id]

async def send_email(user_id, chat_id, message):
    data = users_data.get(user_id)
    if not data:
        return
    
    # Cleaner wait message without HTML formatting
    status_msg = await message.reply("Sending Email Securely...⏳", reply_markup=ReplyKeyboardRemove())
    
    try:
        attachments = []
        # Convert files to Base64 for the API
        for file_path in data.get('files', []):
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                encoded_string = base64.b64encode(f.read()).decode("utf-8")
                attachments.append({
                    "name": file_name,
                    "content": encoded_string
                })

        # Build the JSON payload for Brevo
        payload = {
            "sender": {"name": "Premium Mailer", "email": SENDER_EMAIL},
            "to": [{"email": data['to']}],
            "subject": data['subject'],
            "textContent": data['body']
        }
        
        if attachments:
            payload["attachment"] = attachments

        headers = {
            "accept": "application/json",
            "api-key": EMAIL_API_KEY,
            "content-type": "application/json"
        }

        # Dispatch via async HTTP request
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.brevo.com/v3/smtp/email", 
                json=payload, 
                headers=headers,
                timeout=20 # Built-in timeout so it never hangs!
            ) as response:
                
                if response.status in [200, 201, 202]:
                    # Final success message
                    await status_msg.edit_text("Sent Successfully🥳")
                else:
                    error_data = await response.text()
                    await status_msg.edit_text(f"API Error:\n{error_data}")

    except Exception as e:
        await status_msg.edit_text(f"Failed to send email:\n{e}")
    finally:
        reset_user(user_id)


# --- Bot Handlers ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    reset_user(user_id)
    users_data[user_id] = {'step': 'waiting_email', 'files': []}
    await message.reply(
        "Welcome to the Premium Mailer 💀\n\nSend Receiver's Email✉️", 
        reply_markup=ReplyKeyboardRemove()
    )

@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if user_id not in users_data:
        return

    step = users_data[user_id]['step']

    if step == 'waiting_email':
        if not re.match(r"[^@]+@[^@]+\.[^@]+", text):
            await message.reply("Invalid format. Please Send Receiver's Email✉️")
            return
        users_data[user_id]['to'] = text
        users_data[user_id]['step'] = 'waiting_subject'
        await message.reply("Send Email Subject😶‍🌫️")

    elif step == 'waiting_subject':
        users_data[user_id]['subject'] = text
        users_data[user_id]['step'] = 'waiting_body'
        await message.reply("Send Compose Email👋")

    elif step == 'waiting_body':
        users_data[user_id]['body'] = text
        users_data[user_id]['step'] = 'waiting_file_choice'
        await message.reply("Are U Want To Send Any Files?", reply_markup=file_choice_kb)

    elif step in ['waiting_file_choice', 'waiting_more_files_choice']:
        if text == "Yes":
            users_data[user_id]['step'] = 'waiting_for_file_upload'
            await message.reply("Send File You Want To Attach🙌", reply_markup=ReplyKeyboardRemove())
        elif text == "No" or text == "Continue":
            await send_email(user_id, message.chat.id, message)
        else:
            await message.reply("Please use the menu buttons below.")

@app.on_message(filters.media & filters.private)
async def handle_media(client, message):
    user_id = message.from_user.id
    if user_id not in users_data or users_data[user_id]['step'] != 'waiting_for_file_upload':
        return

    status_msg = await message.reply("Downloading attachment... 📥")
    
    try:
        file_path = await message.download()
        users_data[user_id]['files'].append(file_path)
        
        users_data[user_id]['step'] = 'waiting_more_files_choice'
        await status_msg.delete()
        await message.reply("Are U Want To Attach More Files?", reply_markup=more_files_kb)
    except Exception as e:
        await status_msg.edit_text("Error downloading file. Please try again.")

# --- Web Server for UptimeRobot ---
async def web_handler(request):
    return web.Response(text="Premium Bot is alive and well! 💀")

async def start_webserver():
    web_app = web.Application()
    web_app.router.add_get('/', web_handler)
    runner = web.AppRunner(web_app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port} 😶‍🌫️")

# --- Main Execution ---
async def main():
    await start_webserver()
    await app.start()
    print("API-Powered Bot is up and running! 💀")
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
    
