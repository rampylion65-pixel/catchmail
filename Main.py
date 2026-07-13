import requests
import time
import json
import os
from keep_alive import keep_alive

# ========================= CONFIG =========================
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CHECK_INTERVAL = 10  # seconds
ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), "accounts.txt")
SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_messages.json")
# =======================================================
# =======================================================

keep_alive()  # Start the web server

def load_accounts():
    try:
        with open(ACCOUNTS_FILE, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        print(f"❌ {ACCOUNTS_FILE} not found!")
        return []

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)

def send_to_telegram(email_data, mailbox):
    subject = email_data.get("subject", "No Subject")
    from_addr = email_data.get("from", "Unknown")
    body = email_data.get("text", email_data.get("html", "No content"))[:800]
    date = email_data.get("date", "")

    message = f"""
📬 **New Email!**

**To:** `{mailbox}`
**From:** {from_addr}
**Subject:** {subject}
**Time:** {date}

**Message:**
{body}
    """.strip()

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})

def fetch_full_message(msg_id, address):
    try:
        resp = requests.get(
            f"https://api.catchmail.io/api/v1/message/{msg_id}?mailbox={address}",
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error fetching message {msg_id}: {e}")
    return None

def check_mailbox(address, seen):
    try:
        url = f"https://api.catchmail.io/api/v1/mailbox?address={address}"
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return

        messages = resp.json().get("messages", [])
        if not messages:
            return

        all_ids = [str(msg.get("id")) for msg in messages]
        first_visit = address not in seen

        if first_visit:
            # First time seeing this mailbox:
            # Mark ALL existing messages as seen, but only forward the latest 2
            seen[address] = all_ids  # mark everything as seen upfront

            top2 = messages[:2]  # assume API returns newest first
            for msg in top2:
                msg_id = str(msg.get("id"))
                full_msg = fetch_full_message(msg_id, address)
                if full_msg:
                    send_to_telegram(full_msg, address)
                    print(f"✅ Forwarded (initial top-2): {full_msg.get('subject')}")
        else:
            # Returning visit: forward only messages we haven't seen yet
            for msg in messages:
                msg_id = str(msg.get("id"))
                if msg_id in seen[address]:
                    continue

                full_msg = fetch_full_message(msg_id, address)
                if full_msg:
                    send_to_telegram(full_msg, address)
                    seen[address].append(msg_id)
                    print(f"✅ Forwarded (new): {full_msg.get('subject')}")

    except Exception as e:
        print(f"Error checking {address}: {e}")

# ===================== MAIN =====================
print("🚀 Catchmail Telegram Forwarder Started!")
print("📌 First run: sending latest 2 emails per inbox, then watching for new ones.")

seen_messages = load_seen()

while True:
    accounts = load_accounts()
    print(f"🔍 Checking {len(accounts)} accounts...")

    for account in accounts:
        check_mailbox(account, seen_messages)

    save_seen(seen_messages)
    time.sleep(CHECK_INTERVAL)
