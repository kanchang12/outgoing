from flask import Flask, request, jsonify
import subprocess

app = Flask(__name__)

@app.route('/')
def index():
    return open('index.html').read()

@app.route('/call', methods=['POST'])
def place_call():
    data = request.json
    phone_number = data.get('phoneNumber')
    
    # Call call.py to place the call
    try:
        subprocess.run(["python3", "call.py", phone_number], check=True)
        return jsonify({"message": "Call placed successfully!"})
    except subprocess.CalledProcessError:
        return jsonify({"message": "Error placing the call"}), 500

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8000)
