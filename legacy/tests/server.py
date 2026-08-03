from flask import Flask
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

@sock.route("/ws")
def ws_handler(ws):
    print("WS client connected")

    while True:
        svg_vector = ws.receive()
        if svg_vector is None:
            print("WS client disconnected")
            break
        print(svg_vector)
if __name__ == "__main__":
    app.run(host="10.42.0.23", port=9001, threaded=True, debug=False, use_reloader=False)
