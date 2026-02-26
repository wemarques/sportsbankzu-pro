"use client";

import { useState, useEffect } from "react";

/**
 * Hook customizado para detectar se a tela corresponde a uma media query específica.
 * 
 * @param query - String de media query CSS (ex: "(max-width: 1024px)")
 * @returns boolean - true se a media query corresponder, false caso contrário
 * 
 * @example
 * const isMobile = useMediaQuery("(max-width: 1024px)");
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    // Verificar se estamos no cliente (não no SSR)
    if (typeof window === "undefined") {
      return;
    }

    const mediaQuery = window.matchMedia(query);
    
    // Definir o valor inicial
    setMatches(mediaQuery.matches);

    // Criar listener para mudanças
    const handleChange = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    // Adicionar listener
    mediaQuery.addEventListener("change", handleChange);

    // Cleanup: remover listener quando o componente desmontar
    return () => {
      mediaQuery.removeEventListener("change", handleChange);
    };
  }, [query]);

  return matches;
}
