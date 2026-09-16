"use client";
import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ITENS = [
  { href: "/jogos", rotulo: "Jogos" },
  { href: "/banca", rotulo: "Banca" },
  { href: "/desempenho", rotulo: "Desempenho" },
  { href: "/glossario", rotulo: "Glossário" },
] as const;

/** #257 — celular: barra inferior com 3 (sem Glossário, spec §3); desktop:
 * sidebar com os 4. Um componente, CSS decide o layout por breakpoint — evita
 * duas árvores de link divergindo. Some em "/" (hero), "/login", "/register". */
export function Navegacao() {
  const pathname = usePathname();

  // #257 fix round 1 — evidencia: window.scrollY fica 0 do load ate 1s depois
  // em /glossario#stake, em producao, mobile E chromium (medido com script de
  // diagnostico); o navegador nunca rola para a ancora sozinho porque o corpo
  // chega via streaming RSC (paths do App Router), nao HTML estatico puro no
  // primeiro parse. So passava por acidente: o termo cabia no viewport alto
  // do chromium (elTop 633 < innerHeight 720) mas nao no do celular (elTop
  // 738 > innerHeight 664). scrollIntoView respeita scroll-margin-top (o
  // scroll-mt-4 do termo em glossario/page.tsx), entao nao precisa de offset
  // manual aqui.
  useEffect(() => {
    if (!window.location.hash) return;
    const alvo = document.getElementById(window.location.hash.slice(1));
    alvo?.scrollIntoView({ block: "start" });
  }, [pathname]);

  const ESCONDIDA = new Set(["/", "/login", "/register"]);
  if (ESCONDIDA.has(pathname)) return null;

  return (
    <nav aria-label="navegação principal">
      <ul className="fixed inset-x-0 bottom-0 z-10 flex justify-around border-t border-[var(--sb-linha)] bg-[var(--sb-painel)] py-2 lg:static lg:inset-auto lg:z-auto lg:w-[200px] lg:flex-col lg:gap-1 lg:border-t-0 lg:border-r lg:py-6">
        {ITENS.map((item, i) => (
          <li key={item.href} className={i === 3 ? "hidden lg:block" : ""}>
            <Link
              href={item.href}
              aria-current={pathname.startsWith(item.href) ? "page" : undefined}
              className="sb-foco block rounded-[var(--sb-raio-painel)] px-3 py-2 text-center text-[13px] aria-[current=page]:font-semibold aria-[current=page]:text-[var(--sb-texto)] lg:text-left lg:text-[14px]"
            >
              {item.rotulo}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
