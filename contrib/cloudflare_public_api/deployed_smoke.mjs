const base = process.argv[2];

async function timed(path, options = {}) {
  const started = performance.now();
  const response = await fetch(base + path, options);
  const body = await response.text();
  return {
    status: response.status,
    wall_ms: Number((performance.now() - started).toFixed(2)),
    bytes: Buffer.byteLength(body),
    body,
  };
}

const cases = [
  ["minimal", '[ ] T "Read paper"'],
  ["unicode", '[ ] T "日本語の確認" id:jp_1'],
  ["invalid", '[ ] T "unterminated'],
  ["ten", Array.from({ length: 10 }, (_, i) => `[ ] T "task ${i + 1}" id:t_${i + 1}`).join("\n")],
  ["hundred", Array.from({ length: 100 }, (_, i) => `[ ] T "task ${i + 1}" id:t_${i + 1}`).join("\n")],
  ["fivehundred", Array.from({ length: 500 }, (_, i) => `[ ] T "task ${i + 1}" id:t_${i + 1}`).join("\n")],
];

for (const path of ["/health", "/v1/info"]) {
  console.log(path, JSON.stringify(await timed(path)));
}
for (const [name, text] of cases) {
  const body = JSON.stringify({ text });
  const result = await timed("/v1/check", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  console.log(name, JSON.stringify({
    status: result.status,
    wall_ms: result.wall_ms,
    request_bytes: Buffer.byteLength(body),
    response_bytes: result.bytes,
    result: JSON.parse(result.body),
  }));
}
