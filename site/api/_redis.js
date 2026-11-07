// Tiny Upstash Redis REST client (no dependencies). Connect "Upstash for Redis" to the Vercel project
// (Storage tab); it adds KV_REST_API_URL / KV_REST_API_TOKEN (or UPSTASH_REDIS_REST_URL / _TOKEN).
// Finds the database variables whatever prefix was chosen when connecting it in Vercel
// (KV_REST_API_URL, STORAGE_REST_API_URL, UPSTASH_REDIS_REST_URL, ...). The read-only token is skipped.
function find(suffixes) {
  const env = process.env;
  const key = Object.keys(env).find((k) => !/READ_ONLY/.test(k) && suffixes.some((s) => k.endsWith(s)) && env[k]);
  return key ? env[key] : undefined;
}
const URL_ = find(['_REST_API_URL', 'REDIS_REST_URL']);
const TOKEN = find(['_REST_API_TOKEN', 'REDIS_REST_TOKEN']);

async function pipeline(commands) {
  if (!URL_ || !TOKEN) throw new Error('redis not configured');
  const res = await fetch(URL_.replace(/\/$/, '') + '/pipeline', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + TOKEN, 'Content-Type': 'application/json' },
    body: JSON.stringify(commands),
  });
  if (!res.ok) throw new Error('redis ' + res.status);
  const out = await res.json();
  return out.map((r) => {
    if (r.error) throw new Error(r.error);
    return r.result;
  });
}

module.exports = { pipeline };
