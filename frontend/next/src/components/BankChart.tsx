"use client";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  Title,
  Tooltip,
  Legend,
  CategoryScale,
} from "chart.js";

ChartJS.register(LineElement, PointElement, LinearScale, Title, Tooltip, Legend, CategoryScale);

export default function BankChart({ labels, real, projected }: { labels: string[]; real: number[]; projected: number[] }) {
  const data = {
    labels,
    datasets: [
      {
        label: "Banca Real",
        data: real,
        borderColor: "#10b981",
        backgroundColor: "#10b981",
        tension: 0.25,
      },
      {
        label: "Banca Projetada (EV)",
        data: projected,
        borderColor: "#8b5cf6",
        backgroundColor: "#8b5cf6",
        borderDash: [6, 6],
        tension: 0.25,
      },
    ],
  };
  const options = {
    responsive: true,
    plugins: {
      legend: { labels: { color: "#f1f5f9" } },
      tooltip: { enabled: true },
      title: { display: false },
    },
    scales: {
      x: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.15)" } },
      y: { ticks: { color: "#94a3b8" }, grid: { color: "rgba(148,163,184,0.15)" } },
    },
  } as const;
  return (
    <div className="card p-4">
      <Line data={data} options={options} />
    </div>
  );
}