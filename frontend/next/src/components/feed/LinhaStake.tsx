"use client";
import Link from "next/link";
import type { PickView } from "@/lib/jogoView";
import { useBanca, calcStake } from "@/lib/bancaStore";
import { stake } from "@/lib/copy";

export function LinhaStake({ pick }: { pick: PickView }) {
  const [banca] = useBanca();
  if (banca == null || pick.bookOdd == null) {
    return <p className="text-[14px]"><Link href="/banca" className="sb-foco underline">{stake(null, null)}</Link></p>;
  }
  const valor = calcStake(pick.prob01, pick.bookOdd, banca, pick.classification);
  return (
    <p className="tnum flex justify-between text-[14px]">
      <span>{stake(banca, valor)}</span>
      <Link href="/banca" className="sb-foco underline">ajustar</Link>
    </p>
  );
}
