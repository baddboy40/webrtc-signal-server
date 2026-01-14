#!/usr/bin/env python3
"""
Простой WebRTC сигнальный сервер
Соединяет две стороны для P2P соединения
"""

import asyncio
import json
import logging
from typing import Dict, Set
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
# Ожидающие пары для соединения
waiting_pairs: Set[str] = set()


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
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': f'Client {client_id} already exists'
                        }))
                        continue
                    
                    clients[client_id] = websocket
                    logger.info(f"Client registered: {client_id}")
                    
                    await websocket.send(json.dumps({
                        'type': 'registered',
                        'client_id': client_id
                    }))
                
                elif msg_type == 'offer':
                    # Получен offer от клиента
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
                    offer = data.get('offer')
                    
                    if not target_id or not offer:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Missing target_id or offer'
                        }))
                        continue
                    
                    if target_id not in clients:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': f'Target client {target_id} not found'
                        }))
                        continue
                    
                    # Отправляем offer целевому клиенту
                    target_ws = clients[target_id]
                    await target_ws.send(json.dumps({
                        'type': 'offer',
                        'offer': offer,
                        'from': sender_id
                    }))
                    
                    logger.info(f"Offer forwarded from {sender_id} to {target_id}")
                
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
                    
                    # Отправляем answer целевому клиенту
                    target_ws = clients[target_id]
                    await target_ws.send(json.dumps({
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
                    
                    # Отправляем ICE кандидат целевому клиенту
                    target_ws = clients[target_id]
                    await target_ws.send(json.dumps({
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
        # Удаляем клиента при отключении
        if client_id and client_id in clients:
            del clients[client_id]
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
