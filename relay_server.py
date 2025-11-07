from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room
import uuid, time

app = Flask(__name__)
app.config['SECRET_KEY'] = '123-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

VALID_TOKENS = {
    "device_token": "device1",
    "admin_token": "admin"
}

pending_requests = {}  # Maps request_id to Flask request context waiting for response

@app.route('/run_command', methods=['POST'])
def run_command():
    data = request.json
    token = data.get("token")
    command = data.get("command")
    channel = data.get("channel")

    if token != "admin_token":
        return jsonify({"error": "Unauthorized"}), 403

    request_id = str(uuid.uuid4())
    pending_requests[request_id] = None
    
    data["request_id"] = request_id
    
    socketio.emit('execute_command', data, room=channel)

    # Wait up to 10 seconds for device response
    timeout = 10
    for _ in range(timeout * 10):
        if pending_requests[request_id] is not None:
            result = pending_requests.pop(request_id)
            return jsonify(result)
        time.sleep(0.1)

    pending_requests.pop(request_id, None)
    return jsonify({"error": "Timeout waiting for device"}), 504


@app.route('/test_connect', methods=['POST','GET'])
def run_test():
    return jsonify({"success": "Service is Online"}), 200

@socketio.on('authenticate')
def handle_auth(data):
    token = data.get('token')
    channel = data.get('channel')
    if token not in VALID_TOKENS:
        emit('auth_response', {'status': 'error', 'message': 'Invalid token'})
        return

    emit('auth_response', {'status': 'success', 'channel': channel})
    join_room(channel)
    print(f"{VALID_TOKENS[token]} joined {channel}")


@socketio.on('command_result')
def handle_command_result(data):
    request_id = data.get("request_id")
    output = data.get("output")
    if request_id in pending_requests:
        pending_requests[request_id] = {"status": "ok", "output": output}


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5002)
