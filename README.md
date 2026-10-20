# PotPlayer Discord Rich Presence

PotPlayer eke play wenna film/episode eke nama Discord status eke pennanna hadapu pona script ekak. Windows walata witharai.

## Setup

### 1. Discord Application ekak hadanna
1. https://discord.com/developers/applications ekata gihin **New Application** click karanna.
2. Nama ekak denna. **Meka thamai Discord eke "Playing ..." kiyala pennanne**, eka nisa "PotPlayer" kiyala denna.
3. **General Information** eke thiyena **Application ID** eka copy karanna.

### 2. Python install karanna
- https://www.python.org/downloads/ eken install karanna (install karaddi **Add Python to PATH** tick karanna).

### 3. Package eka install karanna
Command Prompt eke me folder ekata gihin:

```
pip install -r requirements.txt
```

### 4. Application ID eka danna
Option A: `potplayer_rpc.py` eke `YOUR_APPLICATION_ID_HERE` ain karala ID eka danna.

Option B: Command Prompt eke:

```
set DISCORD_CLIENT_ID=oyage_id_eka
python potplayer_rpc.py
```

### 5. Run karanna
1. Discord app eka open karanna.
2. PotPlayer eke film ekak play karanna.
3. Run karanna:

```
python potplayer_rpc.py
```

Dan Discord profile eke "Playing PotPlayer" eka yatin film eke nama pennanawa. Nawathinna **Ctrl+C**.

## Prashna awoth
- **Discord eke pennanne nae**: Settings > Activity Privacy > "Share your detected activity" ON da balanna.
- **Connect wenne nae**: Discord eka (browser eka nowe, desktop app eka) open da balanna. Discord ekai Python ekai ekama permission level eken run karanna (admin/normal).
- **Nama waradi / eka pennanne nae**: PotPlayer window title eka "film nama - PotPlayer" widiyata thiyenna one. PotPlayer eke title format eka wenas karala thiyenawanam script eke `TITLE_SUFFIX` eka adjust karanna.
- Console eka penne nathuwa background eke run karanna ona nam `pythonw potplayer_rpc.py` use karanna.

## Danaganna
- Script eka PotPlayer window eke title eka witharai kiyawanne. Film eka pause karama hari status eka thiyenawa.
- Windows walata witharai wada karanne (ctypes + user32 use karanawa).
