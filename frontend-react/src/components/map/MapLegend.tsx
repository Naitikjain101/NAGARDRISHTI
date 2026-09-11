export function MapLegend() {
  return (
    <div className="absolute bottom-6 right-6 z-[1000] bg-card/90 backdrop-blur-sm border border-border p-4 rounded-lg shadow-lg w-48 text-sm">
      <h3 className="font-semibold mb-3">Legend</h3>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.6)]"></div>
          <span>Pothole</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]"></div>
          <span>Waterlogging</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]"></div>
          <span>Vehicle / Fleet</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]"></div>
          <span>Critical Incident</span>
        </div>
      </div>
    </div>
  );
}
