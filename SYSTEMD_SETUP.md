# Systemd Setup for Regnskap

## Installasjon

1. **Kopier service-filen til systemd:**
```bash
sudo cp regnskap.service /etc/systemd/system/
```

2. **Reload systemd for å laste inn ny service:**
```bash
sudo systemctl daemon-reload
```

3. **Aktiver service (starter automatisk ved oppstart):**
```bash
sudo systemctl enable regnskap.service
```

4. **Start service:**
```bash
sudo systemctl start regnskap.service
```

## Vanlige kommandoer

**Se status:**
```bash
sudo systemctl status regnskap.service
```

**Se logger:**
```bash
sudo journalctl -u regnskap.service -f
```

**Se siste 100 linjer med logger:**
```bash
sudo journalctl -u regnskap.service -n 100
```

**Restart service:**
```bash
sudo systemctl restart regnskap.service
```

**Stopp service:**
```bash
sudo systemctl stop regnskap.service
```

**Deaktiver autostart:**
```bash
sudo systemctl disable regnskap.service
```

## Viktig!

Før du starter servicen, sørg for at:

1. `.env`-filen eksisterer i `/home/andreas/regnskap/` med riktige innstillinger
2. Database er satt opp og kjører
3. Alle Python-pakker er installert (se requirements.txt)

## Feilsøking

Hvis servicen ikke starter:

1. Sjekk logger med: `sudo journalctl -u regnskap.service -n 50`
2. Test manuelt: `cd /home/andreas/regnskap && uvicorn backend.main:app --host 0.0.0.0 --port 8000`
3. Verifiser at .env-filen har riktige verdier
4. Sjekk at MySQL-databasen kjører: `sudo systemctl status mysql`
