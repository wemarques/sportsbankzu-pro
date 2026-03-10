import BankrollCalculator from "@/components/BankrollCalculator";

export const metadata = {
  title: "Gestao de Banca | SportsBankZU Pro",
  description:
    "Distribua sua banca de forma inteligente entre simples, duplas intra e duplas inter usando o criterio de Kelly.",
};

export default function BankrollPage() {
  return <BankrollCalculator />;
}
