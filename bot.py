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
    [[KeyboardButton("Yes"), KeyboardButton("No, Continue")]], 
    resize_keyboard=True, placeholder="Attach a file?"
)

more_files_kb = ReplyKeyboardMarkup(
    [[KeyboardButton("Yes"), KeyboardButton("No, Continue")]], 
    resize_keyboard=True, placeholder="Attach another?"
)

# --- Helper Functions ---
def reset_user(user_id):
    if user_id in users_data:
        # Clean up local files to save disk space
        for file in users_data[user_id].get('files', []):
            if os.path.exists(file):
                try:
                    os.remove(file)
                except:
                    pass
        del users_data[user_id]

# --- The Hidden Background Engine ---
async def dispatch_email_background(user_id, data):
    """This runs silently in the background. The UI doesn't wait for it!"""
    try:
        attachments = []
        for file_path in data.get('files', []):
            if not os.path.exists(file_path):
                continue
            
            # 15MB Safety check
            if os.path.getsize(file_path) > 15 * 1024 * 1024:
                print(f"File too large to send for user {user_id}")
                return 
                
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                encoded_string = base64.b64encode(f.read()).decode("utf-8")
                attachments.append({"name": file_name, "content": encoded_string})

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

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.brevo.com/v3/smtp/email", 
                json=payload, 
                headers=headers,
                timeout=30 
            ) as response:
                print(f"Background Delivery Status: {response.status}")

    except Exception as e:
        print(f"Background Engine Error: {e}")
    finally:
        # Delete the files after sending
        reset_user(user_id)


# --- The UI Controller ---
async def send_email_ui(user_id, message):
    data = users_data.get(user_id)
    if not data:
        return
    
    # 1. Instantly throw the API work to the background
    asyncio.create_task(dispatch_email_background(user_id, data.copy()))
    
    # 2. Skip the "Sending..." message entirely!
    # Instantly drop the success message and remove the keyboard.
    await message.reply("<b>Sent Successfully 🥳🚀</b>", reply_markup=ReplyKeyboardRemove())


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
            await message.reply("Invalid format. Please Send Receiver's Email👇")
            return
        users_data[user_id]['to'] = text
        users_data[user_id]['step'] = 'waiting_subject'
        await message.reply("Send Email Subject👇")

    elif step == 'waiting_subject':
        users_data[user_id]['subject'] = text
        users_data[user_id]['step'] = 'waiting_body'
        await message.reply("Send Compose Email👇")

    elif step == 'waiting_body':
        users_data[user_id]['body'] = text
        users_data[user_id]['step'] = 'waiting_file_choice'
        await message.reply("Are U Want To Send Any Files?", reply_markup=file_choice_kb)

    elif step in ['waiting_file_choice', 'waiting_more_files_choice']:
        if text == "Yes":
            users_data[user_id]['step'] = 'waiting_for_file_upload'
            await message.reply("Send File You Want To Attach🙌", reply_markup=ReplyKeyboardRemove())
        elif text == "No, Continue":
            # Call the UI function directly!
            await send_email_ui(user_id, message)
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
        print(f"Download Error: {e}")
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
