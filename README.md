# WebRTC Signal Server

WebSocket сигнальный сервер для обмена SDP и ICE кандидатами между WebRTC пирами.

## Описание

Проект состоит из двух основных компонентов:
- **signal_server.py** - WebSocket сигнальный сервер для обмена SDP и ICE кандидатами
- **viewer.html** - HTML клиент для просмотра видеопотока в браузере

**GStreamer отправитель** вынесен в отдельную папку `sender/` и может быть запущен независимо.

## Быстрый старт

### Локальное подключение

1. **Запуск сигнального сервера:**
```bash
python3 signal_server.py
```
Сервер запустится на `ws://localhost:8765` (по умолчанию).

2. **Запуск GStreamer отправителя (опционально):**
GStreamer отправитель находится в отдельной папке `../sender/` (на уровень выше основного проекта).
```bash
cd ../sender
python3 web-rtc-gst.py
```
Или используйте Docker (см. раздел "Docker").

3. **Открытие клиента:**
Откройте `viewer.html` в браузере и нажмите "Подключиться".

### Удаленное подключение

#### Настройка сигнального сервера

Сигнальный сервер можно настроить через переменные окружения:

```bash
# Изменить порт (по умолчанию 8765)
export SIGNAL_PORT=8765

# Запуск сервера
python3 signal_server.py
```

Сервер будет слушать на `0.0.0.0:8765`, что позволяет принимать подключения из сети.

#### Настройка GStreamer отправителя

GStreamer отправитель находится в отдельной папке `../sender/` (на уровень выше основного проекта). Настройка подключения:

**Через переменную окружения:**
```bash
export SIGNAL_SERVER_URL=ws://your-server-ip:8765
cd ../sender
python3 web-rtc-gst.py
```

**Или измените URI в коде:**
В файле `../sender/web-rtc-gst.py` измените:
```python
uri = os.getenv('SIGNAL_SERVER_URL', 'ws://your-server-ip:8765')
```

Для использования WSS (защищенного WebSocket) используйте `wss://your-domain.com:8765`.

#### Настройка HTML клиента

В `viewer.html` есть несколько способов указать удаленный сервер:

**Способ 1: Через поле ввода**
- Откройте `viewer.html` в браузере
- В поле "WebSocket Server URL" введите: `ws://your-server-ip:8765`
- Нажмите "Подключиться"

**Способ 2: Через URL параметры**
Откройте страницу с параметрами:
```
viewer.html?ws_host=your-server-ip&ws_port=8765
```

**Способ 3: Изменить код по умолчанию**
В функции `getWebSocketUrl()` измените значения по умолчанию:

```javascript
function getWebSocketUrl() {
    const input = document.getElementById('serverUrl');
    const url = input.value.trim();
    
    if (url) {
        return url;
    }
    
    const urlParams = new URLSearchParams(window.location.search);
    const wsPort = urlParams.get('ws_port') || '8765';
    const wsHost = urlParams.get('ws_host') || 'your-server-ip'; // Измените здесь
    
    return `ws://${wsHost}:${wsPort}`;
}
```

## Требования

### Для сигнального сервера и GStreamer отправителя:

- Python 3.8+
- Зависимости Python:
  ```bash
  pip install websockets
  ```

### Для GStreamer отправителя

GStreamer отправитель находится в отдельной папке `../sender/`. См. `../sender/README.md` для подробных инструкций по установке и настройке.

### Для HTML клиента:

- Современный браузер с поддержкой WebRTC (Chrome, Firefox, Safari, Edge)

## Развертывание на удаленном сервере

### Вариант 1: Прямое подключение

1. **На удаленном сервере:**
   - Установите зависимости (см. раздел "Требования")
   - Запустите `signal_server.py`:
     ```bash
     python3 signal_server.py
     ```
   - Убедитесь, что порт 8765 открыт в файрволе

2. **На локальной машине с камерой:**
   - Перейдите в папку `../sender/` (на уровень выше основного проекта)
   - Установите переменную окружения: `export SIGNAL_SERVER_URL=ws://your-server-ip:8765`
   - Запустите `python3 web-rtc-gst.py`

3. **В браузере:**
   - Откройте `viewer.html`
   - Укажите адрес удаленного сервера в поле подключения

### Вариант 2: Использование Nginx как reverse proxy (рекомендуется)

Для продакшн использования рекомендуется использовать Nginx с SSL для WSS:

**Конфигурация Nginx:**

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Настройка для WSS:**

1. В `web-rtc-gst.py` измените URI:
   ```python
   uri = "wss://your-domain.com"
   ```

2. В `viewer.html` используйте WSS:
   ```
   wss://your-domain.com
   ```

### Вариант 3: Использование systemd для автозапуска

Создайте файл `/etc/systemd/system/webrtc-signal.service`:

```ini
[Unit]
Description=WebRTC Signal Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/webrtc-signal-server
Environment="SIGNAL_PORT=8765"
ExecStart=/usr/bin/python3 /path/to/webrtc-signal-server/signal_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
sudo systemctl enable webrtc-signal.service
sudo systemctl start webrtc-signal.service
```

## Настройка портов и хостов

### Сигнальный сервер

Порт настраивается через переменную окружения:
```bash
export SIGNAL_PORT=8765
python3 signal_server.py
```

Хост по умолчанию: `0.0.0.0` (принимает подключения со всех интерфейсов)

### GStreamer отправитель

Измените URI в функции `signaling_client()`:
```python
uri = "ws://your-server:port"  # или "wss://your-server:port" для SSL
```

### HTML клиент

- Через поле ввода в интерфейсе
- Через URL параметры: `?ws_host=host&ws_port=port`
- Изменив значения по умолчанию в коде

## Безопасность

⚠️ **Важно для продакшн использования:**

1. **Используйте WSS вместо WS** - настройте SSL/TLS через reverse proxy (Nginx)
2. **Ограничьте доступ** - используйте файрвол для ограничения доступа к порту
3. **Аутентификация** - рассмотрите добавление токенов или базовой аутентификации
4. **HTTPS для HTML клиента** - разместите `viewer.html` на HTTPS сервере

## Устранение неполадок

### Ошибка загрузки библиотек GStreamer на macOS

См. `sender/README.md` для решения проблем с GStreamer отправителем.

### Порт уже занят

```bash
# Найти процесс, использующий порт
lsof -i :8765

# Использовать другой порт
export SIGNAL_PORT=8766
python3 signal_server.py
```

### Не удается подключиться к удаленному серверу

1. Проверьте, что порт открыт в файрволе:
   ```bash
   # Linux
   sudo ufw allow 8765/tcp
   
   # macOS
   # Проверьте настройки в System Preferences > Security & Privacy > Firewall
   ```

2. Проверьте доступность сервера:
   ```bash
   telnet your-server-ip 8765
   ```

3. Проверьте логи сервера на наличие ошибок

### Видео не отображается

1. Проверьте консоль браузера на наличие ошибок
2. Убедитесь, что камера доступна на машине с GStreamer отправителем
3. Проверьте, что WebRTC соединение установлено (статус в интерфейсе)

## Структура проекта

```
webrtc-signal-server/
├── signal_server.py      # WebSocket сигнальный сервер
├── viewer.html           # HTML клиент для просмотра
├── requirements.txt      # Зависимости для сигнального сервера
├── Dockerfile            # Docker образ для сигнального сервера
├── docker-compose.yml    # Docker Compose для сигнального сервера
├── nginx.conf            # Конфигурация Nginx (опционально)
├── README.md             # Этот файл
└── sender/               # GStreamer отправитель (отдельный компонент)
    ├── web-rtc-gst.py    # GStreamer приложение для захвата видео
    ├── requirements.txt  # Зависимости для отправителя
    ├── Dockerfile        # Docker образ для отправителя
    ├── docker-compose.yml # Docker Compose для отправителя
    └── README.md          # Инструкции по использованию отправителя
```

## Лицензия

MIT
