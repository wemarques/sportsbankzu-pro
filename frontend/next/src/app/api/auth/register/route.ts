import { NextResponse } from "next/server";
import bcrypt from "bcrypt";
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === "production" ? { rejectUnauthorized: false } : false,
});

export async function POST(req: Request) {
  try {
    const { email, password, name } = await req.json();

    if (!email || !password || !name) {
      return NextResponse.json({ error: "Campos obrigatorios" }, { status: 400 });
    }
    if (password.length < 6) {
      return NextResponse.json({ error: "Senha deve ter no minimo 6 caracteres" }, { status: 400 });
    }

    const { rows: existing } = await pool.query("SELECT id FROM users WHERE email = $1", [email]);
    if (existing.length > 0) {
      return NextResponse.json({ error: "Email ja cadastrado" }, { status: 409 });
    }

    const password_hash = await bcrypt.hash(password, 12);
    const { rows } = await pool.query(
      "INSERT INTO users (email, password_hash, name, role) VALUES ($1, $2, $3, 'free') RETURNING id, email, name, role",
      [email, password_hash, name]
    );

    return NextResponse.json({ user: rows[0] }, { status: 201 });
  } catch (error) {
    console.error("Register error:", error);
    return NextResponse.json({ error: "Erro interno" }, { status: 500 });
  }
}
