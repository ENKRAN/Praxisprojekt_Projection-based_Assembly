from PyQt6.QtWebSockets import QWebSocketServer
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QHostAddress

class RemoteSVGServer(QObject):
    """
    A native PyQt WebSocket server that listens for incoming SVG strings
    from a remote expert (e.g., via a tablet connected through Cloudflare).
    """
    # Signals to communicate with the MainWindow
    svg_received = pyqtSignal(str)
    client_connected = pyqtSignal()
    client_disconnected = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.clients = []
        
        # Just setup the server, but don't start listening yet. We'll call startServer() from MainWindow when we enter Remote Mode.
        self.server = QWebSocketServer("Remote AR Server", QWebSocketServer.SslMode.NonSecureMode, self)
        self.server.newConnection.connect(self.onNewConnection)
        self.server.acceptError.connect(lambda err: print(f"[RemoteServer] Accept error: {err} — {self.server.errorString()}"))
        self.server.serverError.connect(lambda err: print(f"[RemoteServer] Server error: {err} — {self.server.errorString()}"))

    def startServer(self, port: int = 9001, host_ip: str = ""):
        """
        Starts the WebSocket server on the specified port and host IP. If no host IP is provided, it listens on all interfaces (AnyIPv4).
        """
        if not self.server.isListening():
            if not host_ip:
                host_address = QHostAddress.SpecialAddress.AnyIPv4
            else:
                host_address = QHostAddress(host_ip)
                
            if self.server.listen(host_address, port):
                if not host_ip:
                    print(f"[RemoteServer] Successfully started listening on AnyIPv4:{port}.")
                else:
                    print(f"[RemoteServer] Successfully started listening on {host_ip}:{port}.")
            else:
                print(f"[RemoteServer] Error: {self.server.errorString()}")  # Qt-Fehlertext ausgeben

    def stopServer(self):
        """
        Stops the WebSocket server and disconnects all clients. Should be called when exiting Remote Assistance mode.
        """
        if self.server.isListening():
            # Kill all client connections
            for client in self.clients:
                client.close()
            self.clients.clear()
            
            # Stop the server
            self.server.close()
            print("[RemoteServer] Server stopped and port released.")

    def onNewConnection(self):
        """Handles new incoming client connections."""
        client_socket = self.server.nextPendingConnection()
        
        # Connect socket signals to our handler methods
        client_socket.textMessageReceived.connect(self.processTextMessage)
        client_socket.disconnected.connect(self.onClientDisconnected)
        
        self.clients.append(client_socket)
        self.client_connected.emit()
        print("[RemoteServer] Remote expert connected.")

    def processTextMessage(self, message: str):
        """Called whenever the client sends a message (the SVG string)."""
        # We assume the message is a valid SVG string as agreed with the colleague
        self.svg_received.emit(message)

    def onClientDisconnected(self):
        """Cleans up the client reference when they disconnect."""
        sender_socket = self.sender()
        if sender_socket in self.clients:
            self.clients.remove(sender_socket)
            sender_socket.deleteLater()
            
        self.client_disconnected.emit()
        print("[RemoteServer] Remote expert disconnected.")