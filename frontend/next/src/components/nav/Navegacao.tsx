"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAVEGACAO } from "@/lib/copy";

const ITENS = [
  { href: "/jogos", rotulo: NAVEGACAO.jogos },
  { href: "/banca", rotulo: NAVEGACAO.banca },
  { href: "/desempenho", rotulo: NAVEGACAO.desempenho },
  { href: "/glossario", rotulo: NAVEGACAO.glossario },
] as const;

/** #257 — celular: barra inferior com 3 (sem Glossário, spec §3); desktop:
 * sidebar com os 4. Um componente, CSS decide o layout por breakpoint — evita
 * duas árvores de link divergindo. Some em "/" (hero), "/login", "/register". */
export function Navegacao() {
  const pathname = usePathname();

  const ESCONDIDA = new Set(["/", "/login", "/register"]);
  if (ESCONDIDA.has(pathname)) return null;

  return (
    <nav aria-label={NAVEGACAO.rotuloNav} className="lg:sticky lg:top-14 lg:h-[calc(100vh-56px)] lg:w-[200px] lg:self-start lg:overflow-y-auto lg:border-r lg:border-[var(--sb-linha)] lg:bg-[var(--sb-painel)]">
      <ul className="fixed inset-x-0 bottom-0 z-10 flex justify-around border-t border-[var(--sb-linha)] bg-[var(--sb-painel)] py-2 lg:static lg:inset-auto lg:z-auto lg:flex-col lg:justify-start lg:gap-1 lg:border-t-0 lg:bg-transparent lg:py-6">
        {ITENS.map((item, i) => (
          <li key={item.href} className={i === 3 ? "hidden lg:block" : ""}>
            <Link
              href={item.href}
              aria-current={pathname.startsWith(item.href) ? "page" : undefined}
              className="sb-foco block rounded-[var(--sb-raio-painel)] px-3 py-2 text-center text-[13px] aria-[current=page]:font-semibold aria-[current=page]:text-[var(--sb-marca)] lg:text-left lg:text-[14px]"
            >
              {item.rotulo}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
