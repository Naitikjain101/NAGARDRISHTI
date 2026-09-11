import { 
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip, Legend,
  LineChart, Line, XAxis, YAxis, CartesianGrid
} from 'recharts';
import { ChartCard } from '@/components/ui/ChartCard';
import { useRealtimeIncidents } from '@/hooks/useRealtimeIncidents';
import { format } from 'date-fns';

export function Analytics() {
  const { data } = useRealtimeIncidents();
  const incidents = data?.incidents || [];

  // Prepare data for Pie Chart (Incidents by Type)
  const typeCounts = incidents.reduce((acc, curr) => {
    acc[curr.type] = (acc[curr.type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const pieData = Object.entries(typeCounts).map(([name, value]) => ({
    name: name.replace('_', ' ').toUpperCase(),
    value
  }));

  const COLORS = ['#3b82f6', '#f97316', '#10b981', '#ef4444', '#8b5cf6'];

  // Prepare data for Line Chart (Incidents over time, binned by minute/hour)
  // For this simple frontend aggregation, we'll bin by formatted string "HH:mm"
  const timeCounts = incidents.reduce((acc, curr) => {
    const timeKey = format(new Date(curr.created_at), 'HH:mm');
    acc[timeKey] = (acc[timeKey] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Sort by time
  const lineData = Object.entries(timeCounts)
    .sort(([timeA], [timeB]) => timeA.localeCompare(timeB))
    .map(([time, count]) => ({
      time,
      incidents: count
    }));

  return (
    <div className="space-y-6 flex flex-col h-full">
      <div>
        <h1 className="text-2xl font-bold">Data Analytics</h1>
        <p className="text-muted-foreground">Historical trends and distribution of urban incidents.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard 
          title="Incident Distribution" 
          description="Breakdown of active detected events by capability type."
        >
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={80}
                  outerRadius={120}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {pieData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                  itemStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-muted-foreground">
              No data available to chart
            </div>
          )}
        </ChartCard>

        <ChartCard 
          title="Detection Frequency" 
          description="Volume of incidents detected over time."
        >
          {lineData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={lineData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis 
                  dataKey="time" 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis 
                  stroke="hsl(var(--muted-foreground))"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <RechartsTooltip 
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                  itemStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Line 
                  type="monotone" 
                  dataKey="incidents" 
                  stroke="#3b82f6" 
                  strokeWidth={3}
                  dot={{ r: 4, fill: '#3b82f6', strokeWidth: 0 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-muted-foreground">
              No time-series data available
            </div>
          )}
        </ChartCard>
      </div>
    </div>
  );
}
