# ◎ HARMATTAN-LOCATE — Consent-Based Location Sharing

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Ethics](https://img.shields.io/badge/Consent-Required-brightgreen)](#ethics)

**Ethical location-sharing platform** for security labs and authorized social-engineering exercises.  
Share links require **explicit consent** on a clear page. Deceptive “free money” lures are blocked.

> Part of the [HARMATTAN Suite](https://github.com/Life-Is-Nothing/harmattan-suite)

---

## Features

- Unique share links (`/s/<code>`) with expiry & max uses  
- Optional password protection  
- Mandatory consent checkbox  
- Browser GPS only if the user accepts the OS permission prompt  
- Approximate IP geolocation (city/country)  
- Device / browser / timezone metadata  
- Operator dashboard: events, **Leaflet map**, **QR codes**  
- CSV / JSON export  
- Rate limiting  
- Optional alerts via [harmattan-hub](https://github.com/Life-Is-Nothing/harmattan-hub)  

---

## Quick start

```bash
git clone https://github.com/Life-Is-Nothing/harmattan-locate.git
cd harmattan-locate
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install qrcode pillow   # optional QR
./locate.sh
```

- Dashboard: **http://127.0.0.1:8095/ops**  
- Public links: `http://127.0.0.1:8095/s/<code>`

For remote lab participants, set a public base URL:

```bash
export HLOC_HOST=0.0.0.0
export HLOC_PUBLIC_BASE=https://your-tunnel.example
./locate.sh
```

---

## Ethics

**Informed consent only.**  
Do not use deceptive pages or track people without agreement. Unauthorized tracking is illegal.

---

## Author

**Mohamed Adoungouss Ibrahim** · NACF · Niger  
[@Life-Is-Nothing](https://github.com/Life-Is-Nothing)

## License

MIT — see [LICENSE](LICENSE)
