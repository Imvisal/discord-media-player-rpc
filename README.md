# Media RPC (Discord Rich Presence for video players)

Oyage PC eke video player eken play wenna film / TV series episode eka Discord profile eke pennanna hadapu app ekak. Poster eka, season/episode eka, episode nama (series walata) saha "Watching ..." card ekak widiyata pennanawa. **Windows walata witharai.**

## Support karana players
PotPlayer, VLC, KMPlayer, MPC-HC, MPC-BE, SMPlayer, mpv, GOM Player

(Windows Media Player / Windows 11 "Media Player" app eke window title ekata film nama enne nae, nisa eka detect karanna ba.)

## Use karanna (Python one nae, ona PC ekaka wada karanawa)

1. **Releases** page eken latest `MediaRPC.exe` eka download karanna.
2. Hari thanakata (udaharana: `C:\Apps\MediaRPC\`) damma passe double-click karanna. (Auto-start wenne exe eka thiyena thana eken.)
3. Discord **desktop app** eka open karala thiyenna.
4. Oyage player eke film ekak play karanna. Discord profile eke film eke nama poster ekka pennanawa.

Meka wada karanna ona de: Windows + Discord desktop app witharai. Application ID eka app eka ethule thiyenawa, ayema hadanna one nae. Ona kenekta meka copy karala wena PC ekakath run karanna puluwan.

Window eke:
- **Status** (Connected / Discord not found) pennanawa.
- **Now watching** eke player eke nama, film/series eka, poster hamba una da, kiyak welawak balala thiyenawada kiyala pennanawa.
- **Stop / Start** button eken status eka off/on karanna puluwan.

> Windows SmartScreen "unrecognized app" kiyala pennuwoth **More info > Run anyway**. Meka unsigned app ekak nisa enawa.

## System tray saha auto-start
- Window eke **X** click karama app eka close wenne nae, **system tray** ekata (clock eka langa ^ arrow eka) yanawa. Dan wath wada karanawa.
- Tray icon eka **double-click** karoth window eka aye pennanawa. **Right-click** karoth menu eka: Show window, Start/Stop, Start with Windows, **Quit**. Hari ekata app eka nawathinna **Quit** use karanna.
- **Start with Windows** (window eke checkbox eka ho tray menu eka): PC eka on wenakota app eka tray ekata ihimen start wenawa. Palaweni wara app eka run karaddi meka ihimen **ON** wenawa, ona nam off karanna.
- Exe eka aye wena thanakata move karoth, "Start with Windows" off/on karanna.
- App eka dekak ekawara run wenne nae. Aye open karoth "already running" kiyala pennanawa.

## Poster / episode detect wenne kohomada
- File nama eken (`The_Mentalist_S01E01_...mkv`, `Inception.2010.1080p...`, `Show - 05`) series ekakda film ekakda kiyala hoyaganna, quality/release tags (720p, x265, BluRay wage) ain karanawa.
- **TV series**: TVmaze walin (API key one nae) show eke poster eka, ona nam episode eke nama ganna.
- **Film**: iTunes Search walin (API key one nae) poster eka ganna.
- Discord eke "Watching ..." card ekak widiyata poster ekka pennanawa. Internet nathnam / hoyaganna ba unoth poster nathuwa nama witharak pennanawa.
- Nama waradiyata hoyaganna unoth `media_info.py` eke `parse_filename` eka balanna.
- Elapsed time eka pennanne, progress bar ekak nemei (player eke play wena thana window title eken ganna ba).

## Player ekak aluthen add karanna
`players.py` eke `PLAYERS` list ekata line ekak add karanna: player eke nama, exe eke patan ganna akuru, saha window title eke player eke nama (regex).

```python
Player("MyPlayer", ("myplayer",), r"MyPlayer"),
```

## Discord eke pennana nama wenas karanna
Discord eke card eke "Watching **...**" kiyala pennanne **Discord Application** eke nama. https://discord.com/developers/applications > oyage application > **General Information** > **Name** eka (udaharana: "Media Player") wenas karanna. Application ID eka wenas wenne nae.

## Python walin run karanna / exe eka hadanna

```
pip install -r requirements.txt
python media_rpc.py
```

`v` walin patan gannawa tag ekak (udaharanayak: `v1.4.0`) GitHub eke **Releases > Draft a new release** eken publish karama GitHub Actions walin `MediaRPC.exe` build wela **Releases** ekata add wenawa. Tag nathuwa **Actions > Build Windows exe > Run workflow** kalath, build eka **Artifacts** wala download karanna puluwan.

Application ID eka wenas karanna ona nam `media_rpc.py` eke `CLIENT_ID` eka wenas karanna.

## Prashna awoth
- **Discord eke pennanne nae**: Settings > Activity Privacy > "Share your detected activity" ON da balanna.
- **"Discord not found, retrying..." kiyala pennanawa**: Discord desktop app eka open da balanna (browser eka nowe). Discord ekai exe ekai ekama permission level eken run karanna (dekama normal). Discord restart karoth ayeth ihimen connect wenawa.
- **Player eka detect wenne nae**: Window title eka "film nama - Player nama" widiyata thiyenna one, nathnam film eke file nama (extension ekka) witharak title eke thiyenna one. Player eka `players.py` eke list eke thiyenawada balanna.

## Danaganna
- Film eka pause karama hari status eka thiyenawa (window title eken pause detect karanna ba).
- Windows walata witharai wada karanne.
