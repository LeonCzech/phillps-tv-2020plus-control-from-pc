import requests
from requests.auth import HTTPDigestAuth
import json
import base64
import hmac
import hashlib
import sys
import tty
import termios

# --- CONFIG ---
TV_IP = input("Enter TV IP Address: ")
BASE_URL = f"https://{TV_IP}:1926/6"
DEVICE_ID = "mac_client_2026"
# This is the secret found in the AppUtils/PTA logic of the official APK
# It is the "Master" key for the HMAC-SHA1 signature.
PTA_MASTER_SECRET = "ZjkxY2IzYmI3OTY3YmU0MGY1YzdhZTM1YmY0NGE1YjU4Y2ZmYmI4ZGY4ZWIyMDZlYjljMTk2M2Y4YmI1ODljNQ=="

requests.packages.urllib3.disable_warnings()

def get_pta_signature(timestamp, pin):
    """
    Implements com.tpvision.philipstvapp2.TVEngine.Utils.AppUtils.getHMACSHA1
    The signature is HMAC-SHA1(MasterSecret, timestamp + pin)
    The result is converted to HEX (lowercase) and then BASE64 encoded.
    """
    key = base64.b64decode(PTA_MASTER_SECRET)
    message = (str(timestamp) + pin).encode('utf-8')
    
    # Generate HMAC-SHA1
    signature_bytes = hmac.new(key, message, hashlib.sha1).digest()
    
    # TP Vision Logic: Hexadecimal representation of the SHA1 hash
    signature_hex = signature_bytes.hex().lower()
    
    # Final step: Base64 encode the resulting hex string
    return base64.b64encode(signature_hex.encode('utf-8')).decode('utf-8')

def pair():
    print(f"[*] Starting 'TvPairGrantNew' logic for {TV_IP}...")
    try:
        # We mimic the official App ID and requested features
        r1 = requests.post(f"{BASE_URL}/pair/request", json={
            "scope": ["read", "write", "control"],
            "device": {"id": DEVICE_ID, "name": "macOS Remote", "type": "Desktop"},
            "app": {"id": "org.droidtv.videofusion", "name": "VideoFusion", "app_id": "1"}
        }, verify=False, timeout=5)
        
        data = r1.json()
        auth_key = data['auth_key']
        timestamp = data['timestamp']
    except Exception as e:
        print(f"[!] Request failed: {e}")
        sys.exit()
    
    print(f"\n[!] PIN required. Enter code from TV screen.")
    pin = input("PIN: ")

    # Generate the signature from the 'AppUtils' logic
    signature = get_pta_signature(timestamp, pin)

    payload = {
        "auth": {
            "auth_key": auth_key,
            "timestamp": timestamp,
            "signature": signature,
            "pin": pin
        },
        "device": {"id": DEVICE_ID, "name": "macOS Remote", "type": "Desktop"}
    }

    print(f"[*] Attempting Grant (TvPairGrantNew)...")
    # Headers found in the official app
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "TPVision/PhilipsTV",
        "X-Auth-Signature": signature # Some newer models require it in a header too
    }

    # IMPORTANT: The official app uses the 'auth_key' as the Digest Password
    # but the 'DEVICE_ID' as the username.
    r2 = requests.post(f"{BASE_URL}/pair/grant", 
                       json=payload, 
                       headers=headers,
                       auth=HTTPDigestAuth(DEVICE_ID, auth_key), 
                       verify=False)

    if r2.status_code == 200:
        print("[✔] SUCCESS! Paired.")
        return auth_key
    else:
        print(f"[x] Grant Denied ({r2.status_code}). TV response: {r2.text}")
        sys.exit()

def send_key(key, auth_pass):
    try:
        requests.post(f"{BASE_URL}/input/key", json={"key": key}, 
                      auth=HTTPDigestAuth(DEVICE_ID, auth_pass), verify=False, timeout=1)
    except: pass

def remote_loop(auth_pass):
    print("\n--- MAC REMOTE READY ---")
    print("w/a/s/d: Arrows | f: OK | b: Back | h: Home | v/V: Vol | q: Quit")
    mapping = {'w':'CursorUp','s':'CursorDown','a':'CursorLeft','d':'CursorRight','f':'Confirm','b':'Back','h':'Home','v':'VolumeDown','V':'VolumeUp'}
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == 'q': break
            if ch in mapping: send_key(mapping[ch], auth_pass)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

if __name__ == "__main__":
    auth_token = pair()
    remote_loop(auth_token)
