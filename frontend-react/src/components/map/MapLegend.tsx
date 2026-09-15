export function MapLegend() {
  return (
    <div className="absolute bottom-6 right-6 z-[1000] bg-card border border-border p-3 rounded shadow-sm w-44 text-xs font-medium">
      <h3 className="font-bold mb-2 uppercase tracking-wide text-[10px] text-muted-foreground">Legend</h3>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-orange-500"></div>
          <span>Pothole</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-500"></div>
          <span>Waterlogging</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500"></div>
          <span>Vehicle / Fleet</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500"></div>
          <span>Critical Incident</span>
        </div>
      </div>
    </div>
  );
}
