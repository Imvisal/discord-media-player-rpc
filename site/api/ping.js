// POST /api/ping  { id, v, os }  - the app says "this install is running".
// Stores only: a random install id, the app version, "windows" and the time. No titles, no IP.
const { pipeline } = require('./_redis');

const ID = /^[0-9a-f]{32}$/;
const VERSION = /^\d{1,3}\.\d{1,3}\.\d{1,3}$/;

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ ok: false });
  let body = req.body;
  if (typeof body === 'string') {
    try { body = JSON.parse(body); } catch (e) { body = null; }
  }
  const id = body && String(body.id || '');
  const version = body && String(body.v || '');
  if (!ID.test(id) || !VERSION.test(version)) return res.status(400).json({ ok: false });
  const now = Date.now();
  try {
    await pipeline([
      ['ZADD', 'mr:seen', now, id],
      ['HSET', 'mr:ver', id, version],
      ['HSETNX', 'mr:first', id, now],
    ]);
    return res.status(200).json({ ok: true });
  } catch (e) {
    return res.status(503).json({ ok: false });
  }
};
