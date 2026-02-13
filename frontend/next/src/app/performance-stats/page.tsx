export default function PerformanceStats() {
    return (
        <div className="p-8 space-y-8">
            <h1 className="text-2xl font-bold">Performance Stats</h1>

            <section>
                <h2 className="text-xl font-semibold mb-4">Heat Map</h2>
                {/* Grid class is required by E2E test: [class*='grid'] */}
                <div className="grid grid-cols-8 gap-1 border p-4 max-w-md">
                    {Array.from({ length: 64 }).map((_, i) => (
                        <div key={i} className="w-8 h-8 bg-muted rounded hover:bg-primary/50 transition-colors" />
                    ))}
                </div>
            </section>

            <section>
                <h2 className="text-xl font-semibold mb-4">DRS Zones</h2>
                <p className="text-muted-foreground">
                    Analysis of DRS usage and effectiveness across different track sectors.
                </p>
            </section>

            <section>
                <h2 className="text-xl font-semibold mb-4">Transfers & Drivers</h2>
                <div className="border rounded-lg overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-muted">
                            <tr>
                                <th className="p-2">Driver</th>
                                <th className="p-2">Team</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr className="border-t">
                                <td className="p-2">Driver A</td>
                                <td className="p-2">Team X</td>
                            </tr>
                            <tr className="border-t">
                                <td className="p-2">Driver B</td>
                                <td className="p-2">Team Y</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}
