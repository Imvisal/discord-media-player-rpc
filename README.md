# PotPlayer Discord Rich Presence

PotPlayer eke play wenna film/episode eke nama Discord status eke pennanna hadapu app ekak. Windows walata witharai.

## Use karanna (Python one nae)

1. **Releases** page eken latest `PotPlayerRPC.exe` eka download karanna.
2. Discord **desktop app** eka open karala thiyenna.
3. `PotPlayerRPC.exe` double-click karanna. Window eka open wenakotama wada patan gannawa.
4. PotPlayer eke film ekak play karanna. Discord profile eke "Playing PotPlayer" yatin film eke nama pennanawa.

Window eke:
- **Status** (Connected / Discord not found) pennanawa.
- **Now watching** eke dan play wena film eka saha kiyak welawak balala thiyenawada kiyala pennanawa.
- **Stop / Start** button eken status eka off/on karanna puluwan. Window eka close karaddi status eka clear wenawa.

> Windows SmartScreen "unrecognized app" kiyala pennuwoth **More info > Run anyway**. Meka unsigned app ekak nisa enawa.

## Python walin run karanna

```
pip install -r requirements.txt
python potplayer_rpc.py
```

## exe eka hadanne kohomada
`v` walin patan gannawa tag ekak (udaharanayak: `v1.1.0`) push karama (ho GitHub eke **Releases > Draft a new release** eken) GitHub Actions walin `PotPlayerRPC.exe` build wela **Releases** ekata add wenawa. Tag nathuwa **Actions > Build Windows exe > Run workflow** kalath, build eka **Artifacts** wala download karanna puluwan.

## Application ID eka wenas karanna
`potplayer_rpc.py` eke `CLIENT_ID` eka wenas karanna (https://discord.com/developers/applications > oyage application > General Information > Application ID). Application eke **nama** thamai Discord eke "Playing ..." kiyala pennanne.

## Prashna awoth
- **Discord eke pennanne nae**: Settings > Activity Privacy > "Share your detected activity" ON da balanna.
- **"Discord not found, retrying..." kiyala pennanawa**: Discord desktop app eka open da balanna (browser eka nowe). Discord ekai exe ekai ekama permission level eken run karanna (dekama normal). Discord restart karoth ayeth ihimen connect wenawa.
- **Nama waradi / pennanne nae**: PotPlayer window title eka "film nama - PotPlayer" widiyata thiyenna one. Format eka wenas nam script eke `TITLE_SUFFIX` eka adjust karanna.

## Danaganna
- App eka PotPlayer window eke title eka witharai kiyawanne. Film eka pause karama hari status eka thiyenawa.
- Windows walata witharai wada karanne (ctypes + user32 use karanawa).
