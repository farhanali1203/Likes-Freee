from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
import time
from collections import defaultdict
from datetime import datetime
import concurrent.futures
import os
import sys

app = Flask(__name__)

# ✅ Per-key rate limit setup
KEY_LIMIT = 20
token_tracker = defaultdict(lambda: [0, time.time()])

def get_today_midnight_timestamp():
    now = datetime.now()
    midnight = datetime(now.year, now.month, now.day)
    return midnight.timestamp()

def load_tokens(server_name):
    try:
        # Get the directory where the app is running
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        if server_name == "IND":
            file_path = os.path.join(base_dir, "token_ind.json")
        elif server_name in {"BR", "US", "PK", "NA"}:
            file_path = os.path.join(base_dir, "token_pk.json")
        else:
            file_path = os.path.join(base_dir, "token_bd.json")
        
        print(f"Loading tokens from: {file_path}")
        
        if not os.path.exists(file_path):
            print(f"Token file not found: {file_path}")
            # Return dummy tokens for testing
            return [{"token": "dummy_token"}]
            
        with open(file_path, "r") as f:
            data = json.load(f)
            print(f"Loaded {len(data)} tokens")
            return data
    except Exception as e:
        print(f"Error loading tokens: {e}")
        return [{"token": "dummy_token"}]

def encrypt_message(plaintext):
    key = b'Yg&tc%DEuh6%Zc^8'
    iv = b'6oyZDr22E3ychjM%'
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(plaintext, AES.block_size)
    encrypted_message = cipher.encrypt(padded_message)
    return binascii.hexlify(encrypted_message).decode('utf-8')

def create_protobuf_message(user_id, region):
    message = like_pb2.like()
    message.uid = int(user_id)
    message.region = region
    return message.SerializeToString()

def send_request_sync(encrypted_uid, token, url):
    edata = bytes.fromhex(encrypted_uid)
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Authorization': f"Bearer {token}",
        'Content-Type': "application/x-www-form-urlencoded",
        'X-Unity-Version': "2018.4.11f1",
        'ReleaseVersion': "OB52"
    }
    try:
        response = requests.post(url, data=edata, headers=headers, timeout=5)
        return response.status_code
    except Exception as e:
        print(f"Request error: {e}")
        return 500

def send_multiple_requests_sync(uid, server_name, url):
    region = server_name
    protobuf_message = create_protobuf_message(uid, region)
    encrypted_uid = encrypt_message(protobuf_message)
    
    tokens = load_tokens(server_name)
    if not tokens:
        return []
    
    results = []
    # Use ThreadPoolExecutor for concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:  # Reduced to 10 for Vercel
        futures = []
        for i in range(10):  # Only 10 requests
            token = tokens[i % len(tokens)]["token"]
            futures.append(executor.submit(send_request_sync, encrypted_uid, token, url))
        
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result(timeout=10))
            except Exception as e:
                print(f"Thread error: {e}")
                results.append(500)
    
    return results

def create_protobuf(uid):
    message = uid_generator_pb2.uid_generator()
    message.krishna_ = int(uid)
    message.teamXdarks = 1
    return message.SerializeToString()

def enc(uid):
    protobuf_data = create_protobuf(uid)
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

def get_base_url(server_name):
    server_config = {
        "IND": "https://client.ind.freefiremobile.com",
        "BR": "https://client.us.freefiremobile.com",
        "US": "https://client.us.freefiremobile.com",
        "PK": "https://client.pk.freefiremobile.com",
        "NA": "https://client.us.freefiremobile.com",
        "SAC": "https://client.us.freefiremobile.com"
    }
    return server_config.get(server_name, "https://clientbp.ggblueshark.com")

def get_like_url(server_name):
    server_config = {
        "IND": "https://client.ind.freefiremobile.com/LikeProfile",
        "BR": "https://client.us.freefiremobile.com/LikeProfile",
        "US": "https://client.us.freefiremobile.com/LikeProfile",
        "PK": "https://client.pk.freefiremobile.com/LikeProfile",  # ✅ PK Like URL
        "NA": "https://client.us.freefiremobile.com/LikeProfile",
        "SAC": "https://client.us.freefiremobile.com/LikeProfile"
    }
    return server_config.get(server_name, "https://clientbp.ggblueshark.com/LikeProfile")

def make_request(encrypt, server_name, token):
    base_url = get_base_url(server_name)
    url = f"{base_url}/GetPlayerPersonalShow"

    edata = bytes.fromhex(encrypt)
    headers = {
        'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
        'Connection': "Keep-Alive",
        'Accept-Encoding': "gzip",
        'Authorization': f"Bearer {token}",
        'Content-Type': "application/x-www-form-urlencoded",
        'X-Unity-Version': "2018.4.11f1",
        'ReleaseVersion': "OB52"
    }

    try:
        response = requests.post(url, data=edata, headers=headers, timeout=10)
        if response.status_code == 200:
            hex_data = response.content.hex()
            binary = bytes.fromhex(hex_data)
            return decode_protobuf(binary)
        else:
            print(f"Request failed with status: {response.status_code}")
            return None
    except Exception as e:
        print(f"Make request error: {e}")
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except Exception as e:
        print(f"Error decoding Protobuf data: {e}")
        return None

@app.route('/')
def home():
    return jsonify({
        "status": "API is working",
        "message": "Free Fire Like API OB52",
        "endpoints": {
            "like": "/like?uid=UID&server_name=SERVER&key=FarhanXMods"
        },
        "servers": ["IND", "BR", "US", "PK", "NA", "SAC"],
        "version": "OB52"
    })

@app.route('/like', methods=['GET'])
def handle_requests():
    try:
        uid = request.args.get("uid")
        server_name = request.args.get("server_name", "").upper()
        key = request.args.get("key")

        # Log request
        print(f"Request: UID={uid}, Server={server_name}, Key={key}")

        if key != "FarhanXMods":
            return jsonify({"error": "Invalid or missing API key 🔑"}), 403

        if not uid or not server_name:
            return jsonify({"error": "UID and server_name are required"}), 400

        if server_name not in ["IND", "BR", "US", "PK", "NA", "SAC"]:
            return jsonify({"error": f"Invalid server_name. Use: IND, BR, US, PK, NA, SAC"}), 400

        # Load tokens
        tokens_data = load_tokens(server_name)
        
        # Check if using dummy token
        if tokens_data and tokens_data[0].get("token") == "dummy_token":
            return jsonify({
                "success": True,
                "message": "API is working in test mode",
                "LikesGivenByAPI": 10,
                "LikesafterCommand": 100,
                "LikesbeforeCommand": 90,
                "PlayerNickname": "Test_Player",
                "UID": uid,
                "status": 1,
                "remains": f"(20/20)",
                "note": "Please add real token files for production"
            })
            
        token = tokens_data[0]['token']
        encrypt = enc(uid)

        today_midnight = get_today_midnight_timestamp()
        
        tracker_key = f"{token}_{datetime.now().strftime('%Y%m%d')}"
        count, last_reset = token_tracker[tracker_key]

        if last_reset < today_midnight:
            token_tracker[tracker_key] = [0, time.time()]
            count = 0

        if count >= KEY_LIMIT:
            return jsonify({
                "error": "Daily request limit reached for this key.",
                "status": 429,
                "remains": f"(0/{KEY_LIMIT})"
            }), 429

        # Get before like count
        before_result = make_request(encrypt, server_name, token)
        if before_result is None:
            return jsonify({"error": "Failed to fetch player data"}), 500
            
        jsone = MessageToJson(before_result)
        data = json.loads(jsone)
        before_like = int(data.get('AccountInfo', {}).get('Likes', 0))

        # Get like URL based on server
        like_url = get_like_url(server_name)
        print(f"Using Like URL: {like_url} for server: {server_name}")

        # Send like requests using threading
        send_multiple_requests_sync(uid, server_name, like_url)

        # Get after like count
        after_result = make_request(encrypt, server_name, token)
        if after_result is None:
            return jsonify({"error": "Failed to fetch updated player data"}), 500
            
        jsone = MessageToJson(after_result)
        data = json.loads(jsone)

        after_like = int(data.get('AccountInfo', {}).get('Likes', 0))
        id = int(data.get('AccountInfo', {}).get('UID', uid))
        name = str(data.get('AccountInfo', {}).get('PlayerNickname', 'Unknown'))

        like_given = after_like - before_like
        status = 1 if like_given != 0 else 2

        if like_given > 0:
            token_tracker[tracker_key][0] += 1
            count += 1

        remains = KEY_LIMIT - count

        result = {
            "success": True,
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_like,
            "LikesbeforeCommand": before_like,
            "PlayerNickname": name,
            "UID": id,
            "status": status,
            "remains": f"({remains}/{KEY_LIMIT})",
            "server": server_name,
            "version": "OB52"
        }
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in handle_requests: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# For Vercel serverless
app.debug = False

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)