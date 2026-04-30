"use client";

import { AlertTriangle, WifiOff, Calendar, Trophy, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";

export type EmptyStateVariant =
  | "backend-offline"    // Backend indisponivel (503, timeout, etc.)
  | "no-games-date"      // Sem jogos para esta data (backend OK, 0 matches)
  | "no-games-league"    // Liga sem jogos para esta data
  | "mock-dev"           // Mock data em desenvolvimento
  | "client-error";      // Erro de rede do cliente

interface EmptyStateProps {
  variant: EmptyStateVariant;
  errorMessage?: string;
  errorCode?: string;
  dateLabel?: string;
  leagueName?: string;
  onRetry?: () => void;
  onChangeDate?: (direction: "prev" | "next") => void;
}

export default function EmptyState({
  variant,
  errorMessage,
  errorCode,
  dateLabel,
  leagueName,
  onRetry,
  onChangeDate,
}: EmptyStateProps) {
  const config = getConfig(variant, dateLabel, leagueName, errorMessage);

  return (
    <div className="st-empty-state" role="status">
      <div className="st-empty-state__icon">{config.icon}</div>
      <h3 className="st-empty-state__title">{config.title}</h3>
      <p className="st-empty-state__message">{config.message}</p>

      {errorCode && (variant === "backend-offline" || variant === "client-error") && (
        <p className="st-empty-state__error-code" style={{ fontSize: "0.7rem", color: "#888", fontFamily: "monospace", marginTop: 4, userSelect: "all" }}>
          Codigo: {errorCode}
          {errorCode === "API_KEY_ERROR" && (
            <span style={{ display: "block", marginTop: 2, color: "#e67e22" }}>
              Dica: verifique assinatura/pagamento em football-data-api.com e api-football.com
            </span>
          )}
          {errorCode === "HTTP_ERROR" && (
            <span style={{ display: "block", marginTop: 2, color: "#999" }}>
              Dica: verifique se o Lambda esta ativo em AWS Console
            </span>
          )}
          {errorCode === "TIMEOUT" && (
            <span style={{ display: "block", marginTop: 2, color: "#999" }}>
              Dica: Lambda pode estar em cold start — tente em 15s
            </span>
          )}
        </p>
      )}

      {config.suggestion && (
        <p className="st-empty-state__suggestion">{config.suggestion}</p>
      )}

      <div className="st-empty-state__actions">
        {onRetry && (
          <button
            type="button"
            className="st-empty-state__btn st-empty-state__btn--primary"
            onClick={onRetry}
          >
            <RefreshCw size={14} />
            Tentar novamente
          </button>
        )}
        {onChangeDate && (
          <div className="st-empty-state__date-nav">
            <button
              type="button"
              className="st-empty-state__btn st-empty-state__btn--secondary"
              onClick={() => onChangeDate("prev")}
            >
              <ChevronLeft size={14} />
              Data anterior
            </button>
            <button
              type="button"
              className="st-empty-state__btn st-empty-state__btn--secondary"
              onClick={() => onChangeDate("next")}
            >
              Proxima data
              <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** Mock data dev banner — shown inline above matches */
export function MockDataBanner() {
  return (
    <div className="st-mock-banner" role="alert">
      <AlertTriangle size={14} />
      <span>
        <strong>Ambiente de desenvolvimento</strong> — Exibindo dados simulados (mock).
        Dados reais disponiveis apenas em producao.
      </span>
    </div>
  );
}

function getConfig(
  variant: EmptyStateVariant,
  dateLabel?: string,
  leagueName?: string,
  errorMessage?: string,
) {
  switch (variant) {
    case "backend-offline":
      return {
        icon: <WifiOff size={48} strokeWidth={1.5} />,
        title: "Servidor indisponivel",
        message: errorMessage ?? "O servidor de dados esta temporariamente indisponivel.",
        suggestion: "Isso pode acontecer apos uma atualizacao. Aguarde alguns minutos e tente novamente.",
      };
    case "no-games-date":
      return {
        icon: <Calendar size={48} strokeWidth={1.5} />,
        title: `Sem jogos para ${dateLabel ?? "esta data"}`,
        message: "Nenhum jogo agendado para o periodo selecionado.",
        suggestion: "Use as setas para navegar entre datas ou selecione outra liga.",
      };
    case "no-games-league":
      return {
        icon: <Trophy size={48} strokeWidth={1.5} />,
        title: `${leagueName ?? "Liga"} sem jogos`,
        message: `Nenhum jogo encontrado para ${leagueName ?? "esta liga"} neste periodo.`,
        suggestion: "Tente outra data ou verifique se a liga esta em pausa.",
      };
    case "mock-dev":
      return {
        icon: <AlertTriangle size={48} strokeWidth={1.5} />,
        title: "Dados simulados (DEV)",
        message: "Exibindo dados mock para desenvolvimento local.",
        suggestion: "Configure PY_BACKEND_URL para acessar dados reais.",
      };
    case "client-error":
      return {
        icon: <WifiOff size={48} strokeWidth={1.5} />,
        title: "Erro de conexao",
        message: errorMessage ?? "Nao foi possivel conectar ao servidor.",
        suggestion: "Verifique sua conexao com a internet e tente novamente.",
      };
    default:
      return {
        icon: <Calendar size={48} strokeWidth={1.5} />,
        title: "Sem dados",
        message: "Nenhum dado disponivel no momento.",
        suggestion: undefined,
      };
  }
}
