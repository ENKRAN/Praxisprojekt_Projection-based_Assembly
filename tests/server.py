import asyncio
import websockets
import datetime

# Diese Funktion wird für jeden verbundenen Client ausgeführt
async def svg_handler(websocket):
    print("🟢 Client (Browser) verbunden!")
    
    try:
        async for message in websocket:
            # Hier simulieren wir die Verarbeitung
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            size = len(message)
            
            # Ausgabe im Terminal
            print(f"[{timestamp}] SVG empfangen ({size} Bytes)")
            print(f"    Inhalt Vorschau: {message[:60]}...") 

            # Bestätigung an den Browser zurücksenden
            response = f"Server: SVG empfangen um {timestamp}"
            await websocket.send(response)
            
    except websockets.exceptions.ConnectionClosed:
        print("🔴 Verbindung getrennt")

async def main():
    # 'localhost' bedeutet: Nur auf diesem PC erreichbar
    async with websockets.serve(svg_handler, "localhost", 8765):
        print("🚀 Server läuft auf ws://localhost:8765")
        print("   Warte auf Verbindung...")
        await asyncio.Future()  # Hält das Programm am Laufen

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer gestoppt.")