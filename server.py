import json
import logging
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, MediaStreamTrack

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("server.log"),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger(__name__)

peer_connections = {}

class EchoTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        return frame

async def handle_json_message(ws, data):
    logger.info(f"Получено JSON сообщение: {data}")
    if data.get("type") == "WebRTC_OFFER":
        logger.info(f"WebRTC: Получен оффер: {data['offer']}")
        pc = RTCPeerConnection()
        peer_connections[ws] = pc
        
        @pc.on("track")
        async def on_track(track):
            logger.info(f"WebRTC: Получен трек: {track.kind}")
            if track.kind == "audio":
                echo_track = EchoTrack(track)
                pc.addTrack(echo_track)

        offer = RTCSessionDescription(sdp=data["offer"], type="offer")
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        await ws.send_json({"type": "WebRTC_ANSWER", "answer": pc.localDescription.sdp})
        logger.info(f"WebRTC: Отправлен ответ: {pc.localDescription.sdp}")
    elif data.get("type") == "WebRTC_ICE_CANDIDATE":
        logger.info(f"WebRTC: Получен ICE кандидат: {data['candidate']}")
        candidate = RTCIceCandidate(
            sdpMid=data["candidate"]["sdpMid"],
            sdpMLineIndex=data["candidate"]["sdpMLineIndex"],
            candidate=data["candidate"]["candidate"]
        )
        await peer_connections[ws].addIceCandidate(candidate)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logger.info("WebSocket соединение установлено")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await handle_json_message(ws, data)
                except json.JSONDecodeError:
                    logger.error(f"Получено некорректное JSON сообщение: {msg.data}")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket соединение закрыто с ошибкой: {ws.exception()}")
    finally:
        logger.info("WebSocket соединение закрыто")
        if ws in peer_connections:
            await peer_connections[ws].close()
            del peer_connections[ws]

    return ws

app = web.Application()
app.router.add_get('/ws', websocket_handler)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=8080)
