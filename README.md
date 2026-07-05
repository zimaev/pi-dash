# pi-dashboard

Лёгкая стартовая страница мониторинга в духе Mini-Bucket: CPU (общий и по ядрам),
память, температура, диск, сеть, load average. Один backend-файл на Flask + psutil,
один HTML-файл с чистым JS (без Chart.js и прочих тяжёлых либ — графики рисуются
напрямую на canvas).

## Установка на Raspberry Pi

```bash
sudo apt update
sudo apt install -y python3-pip
cd ~
# скопируйте сюда папку pi-dashboard, затем:
cd pi-dashboard
pip3 install -r requirements.txt --break-system-packages
python3 app.py
```

Откройте в браузере: `http://<IP_вашего_Pi>:5000`

## Автозапуск (systemd)

```bash
sudo tee /etc/systemd/system/pi-dashboard.service > /dev/null <<EOF
[Unit]
Description=Pi Dashboard
After=network.target

[Service]
WorkingDirectory=/home/pi/pi-dashboard
ExecStart=/usr/bin/python3 /home/pi/pi-dashboard/app.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now pi-dashboard.service
```

Проверить статус: `sudo systemctl status pi-dashboard`

## Что дальше

Это только стартовая страница. Дальше можно добавлять разделы Mini-Bucket по
одному: диспетчер процессов, файловый менеджер, управление сервисами и т.д. —
каждый как отдельный роут `/api/...` + вкладка в интерфейсе.
