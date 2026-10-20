# PotPlayer Discord Rich Presence

PotPlayer eke play wenna film/episode eke nama Discord status eke pennanna hadapu app ekak. Windows walata witharai.

## Ahala widiya (exe eka use karanna, Python one nae)

1. **Releases** page eken latest `PotPlayerRPC.exe` eka download karanna.
2. Discord desktop app eka open karala thiyenna.
3. PotPlayer eke film ekak play karanna.
4. `PotPlayerRPC.exe` double-click karanna.
5. Palaweni wara Application ID eka ahanawa (yatin eka hoyaganna widiya balanna). Ita passe save wenawa, aye ahanne nae.

Nawathinna console window eka close karanna (ho Ctrl+C).

> Windows SmartScreen "unrecognized app" kiyala pennuwoth **More info > Run anyway**. Meka unsigned app ekak nisa enawa.

### Application ID eka hoyaganna widiya
1. https://discord.com/developers/applications ekata gihin **New Application** click karanna.
2. Nama ekak denna. **Meka thamai Discord eke "Playing ..." kiyala pennanne**, eka nisa "PotPlayer" kiyala denna.
3. **General Information** eke thiyena **Application ID** eka copy karanna.

ID eka wenas karanna one nam `%APPDATA%\PotPlayerRPC\config.json` eka delete karanna, aye ahanawa.

## exe eka nethuwa Python walin run karanna

```
pip install -r requirements.txt
python potplayer_rpc.py
```

(Python install karaddi **Add Python to PATH** tick karanna.)

## exe eka hadanne kohomada
`v` walin patan gannawa tag ekak (udaharanayak: `v1.0.0`) push karama GitHub Actions walin `PotPlayerRPC.exe` build wela **Releases** ekata add wenawa. Tag nathuwa **Actions > Build Windows exe > Run workflow** kalath, build eka **Artifacts** wala download karanna puluwan.

## Prashna awoth
- **Discord eke pennanne nae**: Settings > Activity Privacy > "Share your detected activity" ON da balanna.
- **Connect wenne nae**: Discord desktop app eka open da balanna (browser eka nowe). Discord ekai exe ekai ekama permission level eken run karanna (dekama normal).
- **Nama waradi / pennanne nae**: PotPlayer window title eka "film nama - PotPlayer" widiyata thiyenna one. Format eka wenas nam script eke `TITLE_SUFFIX` eka adjust karanna.

## Danaganna
- App eka PotPlayer window eke title eka witharai kiyawanne. Film eka pause karama hari status eka thiyenawa.
- Windows walata witharai wada karanne (ctypes + user32 use karanawa).
