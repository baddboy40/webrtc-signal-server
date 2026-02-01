#!/usr/bin/env python3
"""
Простой WebRTC сигнальный сервер
Соединяет две стороны для P2P соединения
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional
try:
    # Новая версия websockets (14.0+)
    from websockets.asyncio.server import serve
except ImportError:
    # Старая версия websockets
    from websockets import serve
from websockets.exceptions import ConnectionClosed

# Кастомный фильтр для подавления некритичных ошибок websockets
class WebSocketErrorFilter(logging.Filter):
    def filter(self, record):
        # Подавляем ошибки парсинга HTTP запросов (healthcheck и т.д.)
        error_msg = str(record.getMessage()).lower()
        # Также проверяем имя логгера
        logger_name = record.name.lower()
        
        # Подавляем ошибки от websockets логгеров
        if 'websockets' in logger_name:
            if any(keyword in error_msg for keyword in [
                "invalid message", "http request", "eof", 
                "connection closed while reading", "opening handshake failed",
                "did not receive a valid http request", "stream ends",
                "connection closed", "handshake"
            ]):
                return False  # Не логируем
        
        return True  # Логируем остальное

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Применяем фильтр ко всем логгерам websockets
websockets_logger = logging.getLogger('websockets')
websockets_logger.addFilter(WebSocketErrorFilter())
websockets_logger.setLevel(logging.ERROR)  # Только критические ошибки

websockets_server_logger = logging.getLogger('websockets.server')
websockets_server_logger.addFilter(WebSocketErrorFilter())
websockets_server_logger.setLevel(logging.ERROR)

# Подавляем конкретные ошибки парсинга
logging.getLogger('websockets.http11').addFilter(WebSocketErrorFilter())
logging.getLogger('websockets.http11').setLevel(logging.CRITICAL)
logging.getLogger('websockets.asyncio.server').addFilter(WebSocketErrorFilter())
logging.getLogger('websockets.asyncio.server').setLevel(logging.ERROR)
logging.getLogger('websockets.streams').addFilter(WebSocketErrorFilter())
logging.getLogger('websockets.streams').setLevel(logging.CRITICAL)

# Хранилище подключенных клиентов
clients: Dict[str, 'WebSocket'] = {}
# Комнаты: room_id -> множество client_id
rooms: Dict[str, Set[str]] = {}
# Клиент -> комната (для быстрой проверки)
client_rooms: Dict[str, str] = {}


def _client_in_room(client_id: str) -> Optional[str]:
    """Возвращает room_id клиента или None."""
    return client_rooms.get(client_id)


def _same_room_or_no_room(sender_id: str, target_id: str) -> bool:
    """True если можно переслать (оба в одной комнате или оба без комнаты)."""
    sr = _client_in_room(sender_id)
    tr = _client_in_room(target_id)
    if sr is None and tr is None:
        return True
    if sr is None or tr is None:
        return False
    return sr == tr


async def handle_client(websocket):
    """Обработка подключения клиента"""
    # В новых версиях websockets (14.0+) path доступен через websocket.path
    # Для совместимости со старыми версиями используем getattr
    path = getattr(websocket, 'path', None)
    client_id = None
    
    try:
        # Регистрация клиента
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get('type')
                
                if msg_type == 'register':
                    # Регистрация нового клиента
                    client_id = data.get('client_id')
                    if not client_id:
                        client_id = f"client_{id(websocket)}"
                    
                    if client_id in clients:
                        try:
                            await clients[client_id].close()
                        except Exception:
                            pass
                        logger.info(f"Replacing connection for client: {client_id}")
                    clients[client_id] = websocket
                    logger.info(f"Client registered: {client_id}")
                    
                    await websocket.send(json.dumps({
                        'type': 'registered',
                        'client_id': client_id
                    }))
                
                elif msg_type == 'join_room':
                    room_id = data.get('room_id')
                    if not room_id:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Missing room_id'
                        }))
                        continue
                    sender_id = None
                    for cid, ws in clients.items():
                        if ws == websocket:
                            sender_id = cid
                            break
                    if not sender_id:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Client not registered. Please register first.'
                        }))
                        continue
                    if room_id not in rooms:
                        rooms[room_id] = set()
                    if sender_id in client_rooms:
                        old_room = client_rooms[sender_id]
                        rooms[old_room].discard(sender_id)
                        if not rooms[old_room]:
                            del rooms[old_room]
                    rooms[room_id].add(sender_id)
                    client_rooms[sender_id] = room_id
                    logger.info(f"Client {sender_id} joined room {room_id}")
                    await websocket.send(json.dumps({
                        'type': 'room_joined',
                        'room_id': room_id,
                        'client_id': sender_id
                    }))
                
                elif msg_type == 'leave_room':
                    room_id = data.get('room_id')
                    sender_id = None
                    for cid, ws in clients.items():
                        if ws == websocket:
                            sender_id = cid
                            break
                    if not sender_id:
                        continue
                    if sender_id in client_rooms and client_rooms[sender_id] == room_id:
                        rooms[room_id].discard(sender_id)
                        del client_rooms[sender_id]
                        if not rooms[room_id]:
                            del rooms[room_id]
                        logger.info(f"Client {sender_id} left room {room_id}")
                        await websocket.send(json.dumps({
                            'type': 'room_left',
                            'room_id': room_id
                        }))
                
                elif msg_type == 'offer':
                    sender_id = None
                    for cid, ws in clients.items():
                        if ws == websocket:
                            sender_id = cid
                            break
                    if not sender_id:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Client not registered. Please register first.'
                        }))
                        continue
                    offer = data.get('offer')
                    if not offer:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Missing offer'
                        }))
                        continue
                    room_id = data.get('room_id')
                    target_id = data.get('target_id')
                    msg = {'type': 'offer', 'offer': offer, 'from': sender_id}
                    if room_id:
                        if room_id not in rooms or sender_id not in rooms[room_id]:
                            await websocket.send(json.dumps({
                                'type': 'error',
                                'message': f'Sender not in room {room_id}'
                            }))
                            continue
                        sent = 0
                        for cid in rooms[room_id]:
                            if cid != sender_id and cid in clients:
                                await clients[cid].send(json.dumps(msg))
                                sent += 1
                        logger.info(f"Offer broadcast from {sender_id} to room {room_id} ({sent} clients)")
                    elif target_id:
                        if target_id not in clients:
                            await websocket.send(json.dumps({
                                'type': 'error',
                                'message': f'Target client {target_id} not found'
                            }))
                            continue
                        if not _same_room_or_no_room(sender_id, target_id):
                            await websocket.send(json.dumps({
                                'type': 'error',
                                'message': f'Target {target_id} not in the same room'
                            }))
                            continue
                        await clients[target_id].send(json.dumps(msg))
                        logger.info(f"Offer forwarded from {sender_id} to {target_id}")
                    else:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Missing room_id or target_id'
                        }))
                
                elif msg_type == 'answer':
                    # Получен answer от клиента
                    # Находим client_id по websocket соединению
                    sender_id = None
                    for cid, ws in clients.items():
                        if ws == websocket:
                            sender_id = cid
                            break
                    
                    if not sender_id:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Client not registered. Please register first.'
                        }))
                        continue
                    
                    target_id = data.get('target_id')
                    answer = data.get('answer')
                    
                    if not target_id or not answer:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Missing target_id or answer'
                        }))
                        continue
                    
                    if target_id not in clients:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': f'Target client {target_id} not found'
                        }))
                        continue
                    if not _same_room_or_no_room(sender_id, target_id):
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': f'Target {target_id} not in the same room'
                        }))
                        continue
                    await clients[target_id].send(json.dumps({
                        'type': 'answer',
                        'answer': answer,
                        'from': sender_id
                    }))
                    logger.info(f"Answer forwarded from {sender_id} to {target_id}")
                
                elif msg_type == 'ice-candidate':
                    # Получен ICE кандидат
                    # Находим client_id по websocket соединению
                    sender_id = None
                    for cid, ws in clients.items():
                        if ws == websocket:
                            sender_id = cid
                            break
                    
                    if not sender_id:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Client not registered. Please register first.'
                        }))
                        continue
                    
                    target_id = data.get('target_id')
                    candidate = data.get('candidate')
                    
                    if not target_id or not candidate:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Missing target_id or candidate'
                        }))
                        continue
                    
                    if target_id not in clients:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': f'Target client {target_id} not found'
                        }))
                        continue
                    if not _same_room_or_no_room(sender_id, target_id):
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': f'Target {target_id} not in the same room'
                        }))
                        continue
                    await clients[target_id].send(json.dumps({
                        'type': 'ice-candidate',
                        'candidate': candidate,
                        'from': sender_id
                    }))
                    logger.info(f"ICE candidate forwarded from {sender_id} to {target_id}")
                
                elif msg_type == 'list-clients':
                    # Список всех подключенных клиентов
                    client_list = [cid for cid in clients.keys() if cid != client_id]
                    await websocket.send(json.dumps({
                        'type': 'client-list',
                        'clients': client_list
                    }))
                
                else:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': f'Unknown message type: {msg_type}'
                    }))
            
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': str(e)
                }))
    
    except ConnectionClosed as e:
        if client_id:
            logger.info(f"Client disconnected: {client_id}")
    except Exception as e:
        # Игнорируем ошибки некорректных подключений (healthcheck и т.д.)
        error_msg = str(e).lower()
        if not any(keyword in error_msg for keyword in ["invalid message", "http request", "eof", "connection closed", "handshake"]):
            logger.error(f"Connection error: {e}", exc_info=True)
    finally:
        if client_id and client_id in clients and clients[client_id] == websocket:
            del clients[client_id]
            if client_id in client_rooms:
                room_id = client_rooms[client_id]
                rooms[room_id].discard(client_id)
                if not rooms[room_id]:
                    del rooms[room_id]
                del client_rooms[client_id]
            logger.info(f"Client removed: {client_id}")


async def main():
    """Запуск сигнального сервера"""
    import os
    host = '0.0.0.0'
    port = int(os.getenv('SIGNAL_PORT', '8765'))
    
    # Проверяем доступность порта перед запуском
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
        sock.close()
    except OSError as e:
        if e.errno == 48:  # Address already in use
            logger.error(f"Порт {port} уже занят. Попробуйте:")
            logger.error(f"  1. Остановить другой процесс на порту {port}")
            logger.error(f"  2. Использовать другой порт: SIGNAL_PORT=8766 python3 signal_server.py")
            logger.error(f"  3. Найти процесс: lsof -i :{port}")
        raise
    
    logger.info(f"Starting WebRTC signal server on {host}:{port}")
    
    # Убираем process_request - фильтр логов уже обрабатывает некорректные подключения
    async with serve(handle_client, host, port, reuse_address=True):
        await asyncio.Future()  # Запуск навсегда


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped")
