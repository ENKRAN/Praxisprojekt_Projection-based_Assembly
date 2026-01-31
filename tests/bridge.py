import asyncio
import websockets

# Die Adresse des Ziel-Servers (wo die Daten am Ende hin sollen)
TARGET_SERVER_URI = "ws://localhost:8765"

async def bridge_handler(browser_ws):
    print("🟢 Browser hat sich mit Python-Skript verbunden.")
    
    # Wir öffnen eine Verbindung zum Ziel-Server
    async with websockets.connect(TARGET_SERVER_URI) as target_ws:
        try:
            # Wir warten auf Nachrichten vom Browser
            async for message in browser_ws:
                print(f"🟡 Python-Skript: SVG vom Browser erhalten ({len(message)} Bytes).")
                
                # HIER: Du kannst das SVG jetzt bearbeiten oder speichern, bevor du es sendest
                # z.B.: with open("temp.svg", "w") as f: f.write(message)
                
                print("🟡 Python-Skript: Leite weiter an Ziel-Server...")
                await target_ws.send(message)
                
                # Antwort vom Ziel-Server holen
                response = await target_ws.recv()
                
                # Antwort zurück an den Browser geben
                await browser_ws.send(f"Python-Bridge: Habe es weitergeleitet. Server sagt: {response}")
                
        except websockets.exceptions.ConnectionClosed:
            print("⚪ Browser Verbindung getrennt.")

async def main():
    # Wir starten einen lokalen Server für die HTML-Seite auf Port 5555
    async with websockets.serve(bridge_handler, "localhost", 5555):
        print("🌉 Python-Bridge läuft auf Port 5555 (Wartet auf Browser)...")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ConnectionRefusedError:
        print("❌ Fehler: Der Ziel-Server (Port 8765) läuft nicht!")