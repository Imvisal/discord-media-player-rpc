// GET /api/stats  (header x-admin-key: <ADMIN_PASSWORD>)  - numbers for the admin page.
const crypto = require('crypto');
const { pipeline } = require('./_redis');

const MIN = 60 * 1000, HOUR = 60 * MIN, DAY = 24 * HOUR;
const TZ_OFFSET = 5.5 * HOUR;               // Sri Lanka, for the "new per day" buckets

function same(a, b) {
  const x = crypto.createHash('sha256').update(String(a)).digest();
  const y = crypto.createHash('sha256').update(String(b)).digest();
  return crypto.timingSafeEqual(x, y);
}

function pairs(flat) {                       // ["a","1","b","2"] -> {a:"1", b:"2"}
  const out = {};
  for (let i = 0; i + 1 < (flat || []).length; i += 2) out[flat[i]] = flat[i + 1];
  return out;
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const password = process.env.ADMIN_PASSWORD;
  if (!password) return res.status(503).json({ error: 'ADMIN_PASSWORD is not set in Vercel' });
  if (!same(req.headers['x-admin-key'] || '', password)) return res.status(401).json({ error: 'wrong password' });

  const now = Date.now();
  try {
    const r = await pipeline([
      ['ZCARD', 'mr:seen'],
      ['ZCOUNT', 'mr:seen', now - 45 * MIN, '+inf'],
      ['ZCOUNT', 'mr:seen', now - DAY, '+inf'],
      ['ZCOUNT', 'mr:seen', now - 7 * DAY, '+inf'],
      ['ZCOUNT', 'mr:seen', now - 30 * DAY, '+inf'],
      ['ZRANGE', 'mr:seen', 0, 49, 'REV', 'WITHSCORES'],
      ['HGETALL', 'mr:ver'],
      ['HGETALL', 'mr:first'],
    ]);
    const [total, activeNow, day, week, month, recentFlat, verFlat, firstFlat] = r;
    const ver = pairs(verFlat), first = pairs(firstFlat);

    const versions = {};
    Object.keys(ver).forEach((id) => { versions[ver[id]] = (versions[ver[id]] || 0) + 1; });

    const perDay = {};
    Object.keys(first).forEach((id) => {
      const d = new Date(Number(first[id]) + TZ_OFFSET).toISOString().slice(0, 10);
      perDay[d] = (perDay[d] || 0) + 1;
    });
    const days = [];
    for (let i = 13; i >= 0; i--) {
      const d = new Date(now + TZ_OFFSET - i * DAY).toISOString().slice(0, 10);
      days.push({ day: d, new: perDay[d] || 0 });
    }

    const recent = [];
    for (let i = 0; i + 1 < (recentFlat || []).length; i += 2) {
      const id = recentFlat[i];
      recent.push({ id: id.slice(0, 8), version: ver[id] || '', lastSeen: Number(recentFlat[i + 1]), firstSeen: Number(first[id] || 0) });
    }

    return res.status(200).json({ now, total, activeNow, day, week, month, versions, days, recent });
  } catch (e) {
    return res.status(503).json({ error: 'database is not connected yet (see the setup steps)' });
  }
};
