# Pi-FIDS

Raspberry Pi based Flight Information Display System.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

##Run
python3 fids_display.py

##Secrets
Google Service Account JSON is not included
Place it outside repo and set path via config.py or env vars

---

### ② secrets の正式な置き場所を決める（重要）
**おすすめ構成（実運用向き）**
/home/pi/
secrets/
pi-fids/
service_account.json

`config.py` では：
```python
SERVICE_ACCOUNT_PATH = "/home/pi/secrets/pi-fids/service_account.json"
