
import { NextResponse } from "next/server";

const PY_BACKEND = process.env.PY_BACKEND_URL || "http://127.0.0.1:5001";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

export async function GET() {
  try {
    // Chama o endpoint de live-scores normal, mas vamos confiar que o log no backend
    // (adicionado acima) vai revelar a estrutura no CloudWatch.
    // Mas para ver na tela, precisamos de um endpoint que retorne o raw.
    // Como não posso alterar a rota live-scores para retornar raw (quebraria o app),
    // vou tentar acessar diretamente se houver um endpoint de debug, 
    // ou criar um aqui se eu tivesse acesso ao banco/cache.
    
    // Melhor: Vamos criar uma rota temporária no backend também.
    const res = await fetch(`${PY_BACKEND}/fixtures/debug-live-raw`, {
      cache: "no-store",
    });
    
    if (!res.ok) {
        return NextResponse.json({ error: `Backend returned ${res.status}` }, { status: res.status });
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
