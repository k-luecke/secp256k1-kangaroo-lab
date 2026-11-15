import json
from pathlib import Path

plan = {
    "regime_A_repeatability": {
        "runs": 100,
        "changes": "none",
        "goal": "Measure structural repeatability across nominally identical boots."
    },
    "regime_B_perturbations": [
        {"name":"rtc_plus_1s", "change":"RTC offset +1 second"},
        {"name":"nic_toggle", "change":"NIC disabled vs enabled"},
        {"name":"smp_2", "change":"1 vCPU vs 2 vCPU"},
        {"name":"usb_toggle", "change":"USB controller disabled vs enabled"},
        {"name":"storage_variant", "change":"one virtual storage timing/configuration change"}
    ],
    "regime_C_host_jitter": {
        "runs": 100,
        "changes": "none to guest config; normal host scheduling jitter allowed",
        "goal": "Measure natural VM-to-VM event-topology diversity."
    }
}
Path("boot_plan.json").write_text(json.dumps(plan, indent=2))
print(json.dumps(plan, indent=2))
