import { redirect } from "next/navigation";

export default function Page() {
  redirect("/dashboard");
}

function KeyboardShortcuts({ onSearch }: { onSearch: () => void }) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        onSearch();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onSearch]);
  return null;
}
