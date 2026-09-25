// Liveness probe for the container healthcheck (port 3000). Public: excluded from the auth proxy.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
