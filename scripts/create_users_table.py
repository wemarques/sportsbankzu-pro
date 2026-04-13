"""Create users table for authentication (#136)."""
import os
import sys

def create_table():
    import psycopg2
    DB_URL = os.environ.get("DATABASE_URL", "postgresql://sportsbankpro:SportsBankPro2026@sportsbank-pro-db.c8tmo68mudkb.us-east-1.rds.amazonaws.com:5432/sportsbankpro")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'free' CHECK (role IN ('free', 'plus', 'admin')),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_login TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    """)
    conn.commit()
    print("Tabela users criada com sucesso")
    cur.close()
    conn.close()

def create_admin(email, password, name):
    import psycopg2
    import bcrypt
    DB_URL = os.environ.get("DATABASE_URL", "postgresql://sportsbankpro:SportsBankPro2026@sportsbank-pro-db.c8tmo68mudkb.us-east-1.rds.amazonaws.com:5432/sportsbankpro")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    cur.execute("""
        INSERT INTO users (email, password_hash, name, role)
        VALUES (%s, %s, %s, 'admin')
        ON CONFLICT (email) DO UPDATE SET role = 'admin', password_hash = %s
    """, (email, password_hash, name, password_hash))
    conn.commit()
    print(f"Admin {email} criado/atualizado")
    cur.close()
    conn.close()

if __name__ == "__main__":
    create_table()
    if len(sys.argv) >= 4:
        create_admin(sys.argv[1], sys.argv[2], sys.argv[3])
