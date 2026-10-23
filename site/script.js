/* Live numbers from GitHub Releases. Nothing here is typed in by hand:
   the download count is the sum of GitHub's own download_count for MediaRPC.exe. */
(function () {
  var REPO = 'Imvisal/discord-media-player-rpc';
  var API = 'https://api.github.com/repos/' + REPO + '/releases?per_page=100';
  var ASSET = 'MediaRPC.exe';
  var CACHE_KEY = 'mrpc_release_stats_v1';
  var CACHE_MS = 10 * 60 * 1000;

  var elDownloads = document.getElementById('statDownloads');
  var elVersion = document.getElementById('statVersion');
  var elNote = document.getElementById('statsNote');
  var elFine = document.getElementById('fineVersion');
  var elLabel = document.getElementById('downloadLabel');
  var buttons = [document.getElementById('downloadBtn'), document.getElementById('downloadBtn2')];

  function readCache() {
    try {
      var raw = JSON.parse(sessionStorage.getItem(CACHE_KEY) || 'null');
      if (raw && Date.now() - raw.t < CACHE_MS) return raw.d;
    } catch (e) {}
    return null;
  }
  function writeCache(d) {
    try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ t: Date.now(), d: d })); } catch (e) {}
  }

  function summarize(releases) {
    var total = 0;
    var latest = null;
    releases.forEach(function (r) {
      if (r.draft) return;
      (r.assets || []).forEach(function (a) {
        if (a.name === ASSET) total += a.download_count || 0;
      });
      if (!latest && !r.prerelease) {
        var exe = (r.assets || []).filter(function (a) { return a.name === ASSET; })[0];
        if (exe) latest = { tag: r.tag_name, url: exe.browser_download_url };
      }
    });
    return { total: total, latest: latest };
  }

  function countUp(el, to) {
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || to < 2) { el.textContent = to.toLocaleString(); return; }
    var start = null, dur = 900;
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))).toLocaleString();
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function render(s) {
    countUp(elDownloads, s.total);
    elNote.textContent = 'Live numbers from GitHub Releases.';
    if (s.latest) {
      elVersion.textContent = s.latest.tag;
      elFine.textContent = 'Latest: ' + s.latest.tag + ' · Windows 10/11';
      elLabel.textContent = 'Download ' + s.latest.tag;
      buttons.forEach(function (b) { if (b) b.href = s.latest.url; });
    }
  }

  function fail() {
    // Keep the dashes and the plain "latest release" links; never show a made-up number.
    elNote.textContent = 'Live numbers are unavailable right now.';
  }

  var cached = readCache();
  if (cached) { render(cached); return; }

  fetch(API, { headers: { Accept: 'application/vnd.github+json' } })
    .then(function (res) { if (!res.ok) throw new Error(res.status); return res.json(); })
    .then(function (data) {
      var s = summarize(data);
      writeCache(s);
      render(s);
    })
    .catch(fail);
})();
