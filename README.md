# pi-dashboard

Панель мониторинга и управления для Raspberry Pi / DietPi. Flask-бэкенд с Blueprint-модулями + vanilla JS фронтенд.

**Возможности:**
- **Система** — CPU (общий + по ядрам), память, температура, диск, сеть, load average, аптайм
- **USB-диски** — обнаружение, монтирование/отмонтирование через `udisksctl`
- **Samba** — управление шарами (CRUD), список активных подключений
- **Transmission** — мониторинг закачек: скорость, прогресс, пиры, ETA

## Установка на DietPi (одна команда)

```bash
sudo bash install.sh
```

Скрипт автоматически:
1. Установит системные пакеты (python3, samba, transmission-daemon, udisks2)
2. Создаст Python venv в `/opt/pi-dashboard`
3. Установит Python-зависимости
4. Создаст и запустит systemd-сервис
5. Включит автозапуск после перезагрузки

Откройте в браузере: `http://<IP_вашего_Pi>:5000`

## Установка вручную

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip samba samba-common-bin transmission-daemon udisks2

python3 -m venv /opt/pi-dashboard/venv
/opt/pi-dashboard/venv/bin/pip install -r requirements.txt

# Скопируйте файлы проекта в /opt/pi-dashboard/
sudo bash install.sh  # или настройте systemd вручную
```

## Управление сервисом

```bash
sudo systemctl status pi-dashboard     # статус
sudo systemctl restart pi-dashboard    # перезапуск
sudo journalctl -u pi-dashboard -f     # логи в реальном времени
```

## Конфигурация

Файл `config.json`:

```json
{
    "transmission": {
        "host": "localhost",
        "port": 9091,
        "username": "",
        "password": ""
    },
    "samba": {
        "config_path": "/etc/samba/smb.conf"
    },
    "polling_interval_ms": 2000,
    "port": 5000
}
```

## API

| Эндпоинт | Метод | Описание |
|---|---|---|
| `/api/stats` | GET | Системные метрики |
| `/api/usb` | GET | Список USB-устройств |
| `/api/usb/mount` | POST | Монтирование диска |
| `/api/usb/unmount` | POST | Отмонтирование диска |
| `/api/samba/status` | GET | Статус smbd |
| `/api/samba/shares` | GET | Список шар |
| `/api/samba/shares` | POST | Добавить шару |
| `/api/samba/shares/<name>` | DELETE | Удалить шару |
| `/api/samba/connections` | GET | Активные подключения |
| `/api/transmission/stats` | GET | Глобальная статистика |
| `/api/transmission/torrents` | GET | Список торрентов |

## Структура проекта

```
pi-dashboard/
├── app.py                 # Flask app, Blueprint registry
├── usb.py                 # USB-диски: lsblk + udisksctl
├── samba.py               # Samba: smb.conf + smbstatus
├── transmission.py        # Transmission: RPC мониторинг
├── config.json            # Настройки
├── requirements.txt       # Зависимости
├── install.sh             # Установщик для DietPi
├── pi-dashboard.service   # Systemd unit
└── static/
    └── index.html         # Фронтенд
```

## Зависимости

- Python 3.9+
- Flask, psutil, gunicorn, transmission-rpc
- System: samba, transmission-daemon, udisks2
