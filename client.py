import asyncio
import json
import logging
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer    
from aiortc.mediastreams import MediaStreamTrack
from aiortc import RTCIceCandidate
import websockets
import time
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AudioStreamTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track):
        super().__init__()
        self.track = track
        self.ended = asyncio.Event()

    async def recv(self):
        try:
            frame = await self.track.recv()
            logger.debug(f"Получен аудиофрейм: sample_rate={frame.sample_rate}, time={frame.time}, samples={frame.samples}")
            return frame
        except Exception as e:
            logger.info(f"Передача аудио завершена: {e}")
            self.ended.set()
            raise



async def start_webrtc(websocket):
    pc = RTCPeerConnection()
    player = MediaPlayer('test.wav')
    audio_track = AudioStreamTrack(player.audio)
    pc.addTrack(audio_track)

    @pc.on("icecandidate")
    async def on_icecandidate(event):
        if event.candidate:
            candidate = {
                "candidate": event.candidate.candidate,
                "sdpMid": event.candidate.sdpMid,
                "sdpMLineIndex": event.candidate.sdpMLineIndex,
            }
            await websocket.send(json.dumps({"type": "WebRTC_ICE", "ice": candidate}))

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    await websocket.send(json.dumps({"type": "WebRTC_OFFER", "offer": pc.localDescription.sdp}))

    # Ждем ответа и обрабатываем ICE кандидатов
    answer_received = False
    while not answer_received:
        message = await websocket.recv()
        data = json.loads(message)
        if data['type'] == 'WebRTC_ANSWER':
            answer = RTCSessionDescription(sdp=data['answer'], type='answer')
            await pc.setRemoteDescription(answer)
            answer_received = True
        elif data['type'] == 'WebRTC_ICE':
            candidate = RTCIceCandidate(**data['candidate'])
            await pc.addIceCandidate(candidate)

    # Ожидаем завершения передачи аудио
    await audio_track.ended.wait()

    # Закрытие соединений
    await pc.close()
    await websocket.close()
    print("WebRTC и WebSocket соединения закрыты.")

    return True


async def main():
    uri = "ws://localhost:8080/ws"
    async with websockets.connect(uri) as websocket:
        print(f"Установлено WebSocket соединение с {uri}")
        transfer_completed = await start_webrtc(websocket)
        if transfer_completed:
            print("Передача файла завершена. Завершаем программу.")

if __name__ == "__main__":
    asyncio.run(main())
