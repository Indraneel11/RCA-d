from app.simulator import simulate_requests
from app.storage import read_logs, read_metrics, read_traces


results = simulate_requests(5)

print("Simulation Results:")
for result in results:
    print(result)

print("Total Logs:", len(read_logs()))
print("Total Metrics:", len(read_metrics()))
print("Total Traces:", len(read_traces()))