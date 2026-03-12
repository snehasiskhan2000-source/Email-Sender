import os
import asyncio
import re
import base64
import json
from pyrogram import Client, filters, idle, enums
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
start_kb = ReplyKeyboardMarkup(
    [[KeyboardButton("START👾")]], 
    resize_keyboard=True
)

file_choice_kb = ReplyKeyboardMarkup(
    [[KeyboardButton("Yes"), KeyboardButton("No, Continue")]], 
    resize_keyboard=True, placeholder="Attach a file?"
)

more_files_kb = ReplyKeyboardMarkup(
    [[KeyboardButton("Yes"), KeyboardButton("No, Continue")]], 
    resize_keyboard=True, placeholder="Attach another?"
)

restart_kb = ReplyKeyboardMarkup(
    [[KeyboardButton("Send Another Email 🌚")]], 
    resize_keyboard=True
)

# --- Helper Functions ---
def reset_user(user_id):
    if user_id in users_data:
        for file in users_data[user_id].get('files', []):
            if os.path.exists(file):
                try:
                    os.remove(file)
                except:
                    pass
        del users_data[user_id]

# --- The Hidden Background Engine ---
async def dispatch_email_background(user_id, data):
    """This runs silently in the background."""
    try:
        attachments = []
        for file_path in data.get('files', []):
            if not os.path.exists(file_path):
                continue
            
            if os.path.getsize(file_path) > 15 * 1024 * 1024:
                return 
                
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                encoded_string = base64.b64encode(f.read()).decode("utf-8")
                attachments.append({"name": file_name, "content": encoded_string})

        sender_name = data.get('sender_name', 'Premium Mailer')
        
        payload = {
            "sender": {"name": sender_name, "email": SENDER_EMAIL},
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
        reset_user(user_id)


# --- The UI Controller (The Magic Animation) ---
async def send_email_ui(client, user_id, message):
    data = users_data.get(user_id)
    if not data:
        return
    
    chat_id = message.chat.id
    history = data.get('history', [])
    
    # 1. Throw email task to background
    asyncio.create_task(dispatch_email_background(user_id, data.copy()))
    
    # 2. THE CASCADING ANIMATION: Edit all bot prompts to 🎉 rapidly
    for msg_id in history:
        try:
            # Only bot messages will successfully edit, user messages fail silently
            await client.edit_message_text(chat_id, msg_id, "🎉")
            await asyncio.sleep(0.05) 
        except:
            pass

    # 3. Drop the Confetti Bomb API Hack
    success_text = "<b>Sent Successfully 🥳🚀</b>"
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": str(chat_id),
            "text": success_text,
            "parse_mode": "HTML",
            "message_effect_id": "5046509860389126442", # 🎉 CONFETTI ID
            "reply_markup": {
                "keyboard": [[{"text": "Send Another Email 🌚"}]],
                "resize_keyboard": True
            }
        }
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload)
    except:
        await message.reply(success_text, reply_markup=restart_kb)

    # 4. Wait 2 seconds for the user to admire the fireworks...
    await asyncio.sleep(2)
    
    # 5. NUKE THE HISTORY! Clean the screen entirely.
    try:
        await client.delete_messages(chat_id, history)
    except Exception as e:
        print(f"Cleanup Error: {e}")


# --- Bot Handlers ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    try:
        await message.delete()
    except Exception:
        pass
        
    reset_user(user_id)
    # Initialize the history tracker!
    users_data[user_id] = {'step': 'waiting_start_button', 'files': [], 'history': []}
    
    caption_text = (
        "Welcome to **Premium Mailer** 💀\n\n"
        "The most advanced, secure, and seamless email dispatcher on Telegram."
    )
    
    try:
        await client.send_chat_action(chat_id, enums.ChatAction.TYPING)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        
        form = aiohttp.FormData()
        form.add_field('chat_id', str(chat_id))
        form.add_field('caption', caption_text)
        form.add_field('parse_mode', 'Markdown')
        
        markup = json.dumps({
            "keyboard": [[{"text": "START👾"}]],
            "resize_keyboard": True
        })
        form.add_field('reply_markup', markup)
        form.add_field('message_effect_id', '5104841245755180586') 
        
        with open('welcome.jpg', 'rb') as f:
            form.add_field('photo', f, filename='welcome.jpg')
            async with aiohttp.ClientSession() as session:
                await session.post(url, data=form)
    except Exception:
        await client.send_photo(chat_id=chat_id, photo="welcome.jpg", caption=caption_text, reply_markup=start_kb)

@app.on_message(filters.text & filters.private)
async def handle_text(client, message):
    user_id = message.from_user.id
    text = message.text
    
    # 🔁 RESTART LOGIC
    if text == "Send Another Email 🌚":
        reset_user(user_id)
        users_data[user_id] = {'step': 'waiting_email', 'files': [], 'history': []}
        try:
            await message.delete()
        except:
            pass
        m = await message.reply("Send Receiver's Email 👋", reply_markup=ReplyKeyboardRemove())
        users_data[user_id]['history'].append(m.id)
        return
    
    if user_id not in users_data:
        return

    # Track user's message
    users_data[user_id]['history'].append(message.id)
    step = users_data[user_id]['step']
    
    if step == 'waiting_start_button':
        if text == "START👾":
            users_data[user_id]['step'] = 'waiting_email'
            m = await message.reply("Send Receiver's Email 👋", reply_markup=ReplyKeyboardRemove())
            users_data[user_id]['history'].append(m.id)
        else:
            m = await message.reply("Please tap the **START👾** button below.", reply_markup=start_kb)
            users_data[user_id]['history'].append(m.id)

    elif step == 'waiting_email':
        if not re.match(r"[^@]+@[^@]+\.[^@]+", text):
            m = await message.reply("Invalid format. Please Send Receiver's Email✉️")
            users_data[user_id]['history'].append(m.id)
            return
        users_data[user_id]['to'] = text
        users_data[user_id]['step'] = 'waiting_name'
        m = await message.reply("What's Your Name 📛")
        users_data[user_id]['history'].append(m.id)

    elif step == 'waiting_name':
        users_data[user_id]['sender_name'] = text
        users_data[user_id]['step'] = 'waiting_subject'
        m = await message.reply("Send Email Subject😶‍🌫️")
        users_data[user_id]['history'].append(m.id)

    elif step == 'waiting_subject':
        users_data[user_id]['subject'] = text
        users_data[user_id]['step'] = 'waiting_body'
        m = await message.reply("Send Compose Email👋")
        users_data[user_id]['history'].append(m.id)

    elif step == 'waiting_body':
        users_data[user_id]['body'] = text
        users_data[user_id]['step'] = 'waiting_file_choice'
        m = await message.reply("Are U Want To Send Any Files?", reply_markup=file_choice_kb)
        users_data[user_id]['history'].append(m.id)

    elif step in ['waiting_file_choice', 'waiting_more_files_choice']:
        if text == "Yes":
            users_data[user_id]['step'] = 'waiting_for_file_upload'
            m = await message.reply("Send File You Want To Attach🙌", reply_markup=ReplyKeyboardRemove())
            users_data[user_id]['history'].append(m.id)
        elif text == "No, Continue":
            await send_email_ui(client, user_id, message)
        else:
            m = await message.reply("Please use the menu buttons below.")
            users_data[user_id]['history'].append(m.id)

@app.on_message(filters.media & filters.private)
async def handle_media(client, message):
    user_id = message.from_user.id
    if user_id not in users_data or users_data[user_id]['step'] != 'waiting_for_file_upload':
        return

    users_data[user_id]['history'].append(message.id)
    status_msg = await message.reply("Downloading attachment... 📥")
    users_data[user_id]['history'].append(status_msg.id)
    
    try:
        file_path = await message.download()
        users_data[user_id]['files'].append(file_path)
        users_data[user_id]['step'] = 'waiting_more_files_choice'
        await status_msg.delete()
        
        m = await message.reply("Are U Want To Attach More Files?", reply_markup=more_files_kb)
        users_data[user_id]['history'].append(m.id)
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
    
