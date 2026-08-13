import numpy as np
import matplotlib.pyplot as plt


def calculate_daily_delta(daily_vehicles, rainfall_mm, freeze_thaw_cycles, road_age_years):
    """Calculate one day's worth of severity increase from all three factors."""
    ds_traffic = 0.002 * (daily_vehicles / 1000)
    ds_weather = 0.05 * (rainfall_mm / 100) + 0.03 * freeze_thaw_cycles
    ds_age = 0.001 * (road_age_years / 20)
    return ds_traffic + ds_weather + ds_age


def simulate_30_days(initial_severity, daily_vehicles, rainfall_mm, freeze_thaw_cycles, road_age_years):
    """
    Simulate severity progression over 30 days.
    Returns a list of severity values, one per day (index 0 = day 0/start).
    """
    severities = [initial_severity]
    current_severity = initial_severity

    for day in range(30):
        delta = calculate_daily_delta(daily_vehicles, rainfall_mm, freeze_thaw_cycles, road_age_years)
        current_severity += delta
        severities.append(current_severity)

    return severities


if __name__ == "__main__":
    # test with sample values
    initial_severity = 2.5       # arbitrary starting damage score
    daily_vehicles = 5000        # moderate traffic road
    rainfall_mm = 15             # daily average rainfall
    freeze_thaw_cycles = 0.1     # small chance of freeze-thaw per day
    road_age_years = 8

    result = simulate_30_days(initial_severity, daily_vehicles, rainfall_mm, freeze_thaw_cycles, road_age_years)

    print(f"Day 0 severity: {result[0]:.4f}")
    print(f"Day 30 severity: {result[-1]:.4f}")
    print(f"Total increase: {result[-1] - result[0]:.4f}")

    # plot
    plt.figure(figsize=(8, 5))
    plt.plot(range(31), result, marker='o', markersize=3)
    plt.xlabel("Day")
    plt.ylabel("Severity Score")
    plt.title("Simulated Road Degradation Over 30 Days")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("test_plot.png")
    plt.show()
    print("Plot saved as test_plot.png")