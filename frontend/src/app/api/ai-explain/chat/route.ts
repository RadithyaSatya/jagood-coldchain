const AI_EXPLAIN_API_BASE_URL = process.env.AI_EXPLAIN_API_BASE_URL ?? "http://localhost:8001";

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ detail: "Request body must be valid JSON." }, { status: 400 });
  }

  try {
    const response = await fetch(`${AI_EXPLAIN_API_BASE_URL}/v1/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await response.text();
    return new Response(body, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { detail: "Layanan ringkasan keputusan tidak tersedia." },
      { status: 502 },
    );
  }
}
