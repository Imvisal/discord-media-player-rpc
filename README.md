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

## System tray saha auto-start
- Window eke **X** click karama app eka close wenne nae, **system tray** ekata (clock eka langa ^ arrow eka) yanawa. Dan wath wada karanawa.
- Tray icon eka **double-click** karoth window eka aye pennanawa. **Right-click** karoth menu eka: Show window, Start/Stop, Start with Windows, **Quit**. Hari ekata app eka nawathinna **Quit** use karanna.
- **Start with Windows** (window eke checkbox eka ho tray menu eka): PC eka on wenakota app eka tray ekata ihimen start wenawa. Palaweni wara app eka run karaddi meka ihimen **ON** wenawa, ona nam off karanna.
- Auto-start wenne exe eka thiyena **thana** (path eka) register karala. Nisa exe eka hari thanakata (udaharana: `C:\Apps\PotPlayerRPC\`) damma passe run karanna. Pasuwa ekata move karoth, "Start with Windows" off/on karanna.
- App eka dekak ekawara run wenne nae. Aye open karoth "already running" kiyala pennanawa.

## Poster / episode detect wenne kohomada
- File nama eken (`The_Mentalist_S01E01_...mkv`, `Inception.2010.1080p...`, `Show - 05`) series ekakda film ekakda kiyala hoyaganna, quality/release tags (720p, x265, BluRay wage) ain karanawa.
- **TV series**: TVmaze walin (API key one nae) show eke poster eka, ona nam episode eke nama ganna.
- **Film**: iTunes Search walin (API key one nae) poster eka ganna.
- Discord eke "Watching ..." card ekak widiyata poster ekka pennanawa. Internet nathnam / hoyaganna ba unoth poster nathuwa nama witharak pennanawa.
- Nama waradiyata hoyaganna unoth (udaharana: file eke nama wenas) `media_info.py` eke `parse_filename` eka balanna.
- Elapsed time eka pennanne, progress bar ekak nemei (PotPlayer eken play wena thana ganna ba).

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
