# Bug Report: Severe PCIe ASPM flaw causing soft lockups on SKIKK Thor AMD

## System Information
* **Manufacturer:** SKIKK
* **Product Name:** Thor AMD
* **Operating System:** Ubuntu 25.10 (Questing)
* **Kernel Version:** 6.17.0-23-generic
* **Affected Component:** Realtek Semiconductor Co., Ltd. RTL8125 2.5GbE Controller (PCIe ID: 10ec:8125)

## Issue Summary
When Active State Power Management (ASPM) is enabled by the OS, the Realtek Ethernet controller fails to negotiate power states correctly. This results in an immediate and continuous flood of PCIe Advanced Error Reporting (AER) errors (Data Link and Physical Layer). 

The error flood is so severe that it overwhelms the CPU, causing a `watchdog: BUG: soft lockup - CPU stuck for 22s+` which results in a complete, unrecoverable system freeze.

Following a hard reset from this freeze, the system BIOS frequently disables the Ethernet controller entirely to protect the PCIe bus, requiring a complete cold boot (power disconnected) to restore the hardware.

## Reproduction Steps
1. Boot the system with default kernel parameters (ASPM enabled).
2. The system will either immediately freeze upon reaching the desktop, or freeze shortly after when the PCIe bus attempts to enter an L0s/L1 power state.
3. System requires a hard power cycle.

## Impact
The only viable workaround is to disable ASPM globally by adding `pcie_aspm=off` to the kernel boot parameters. 

While this stabilizes the system and stops the crashes, **it breaks Modern Standby (s2idle).** Because ASPM is disabled globally, the PCIe root ports (including those connected to the NVIDIA dGPU) cannot enter a low-power state. Consequently, the laptop continues to draw significant baseline power, generates heat, and drains the battery rapidly while the lid is closed.

## Troubleshooting Completed
* **Driver Swap:** The issue was initially observed on the in-kernel `r8169` driver. We subsequently installed the official Realtek `r8125-dkms` (v9.016.01) driver and blacklisted `r8169`. The hardware crash and soft lockup still occur the moment ASPM is enabled, proving this is not a driver-level issue.
* **GPU Isolation:** We have verified that the NVIDIA dGPU (RTX 5070 Ti) suspends perfectly via `NVreg_DynamicPowerManagement=0x02`. The heat issue during sleep is entirely isolated to the PCIe lanes remaining active due to the forced `pcie_aspm=off` workaround.

## Example Kernel Log Output (During Crash)
```text
pcieport 0000:00:01.6: AER: Multiple Correctable error message received from 0000:00:01.6
r8125 0000:05:00.0: PCIe Bus Error: severity=Correctable, type=Data Link Layer, (Transmitter ID)
r8125 0000:05:00.0:   device [10ec:8125] error status/mask=00001100/0000e000
r8125 0000:05:00.0:    [ 8] Rollover              
r8125 0000:05:00.0:    [12] Timeout               
r8125 0000:05:00.0: PCIe Bus Error: severity=Correctable, type=Physical Layer, (Receiver ID)
r8125 0000:05:00.0:   device [10ec:8125] error status/mask=0001243f/00001100
r8125 0000:05:00.0:    [ 0] RxErr                  (First)
watchdog: BUG: soft lockup - CPU#9 stuck for 22s! [kworker/9:2:206293]
```

## Request
This appears to be an ACPI/Firmware flaw regarding how the PCIe root port handles ASPM handshakes with this specific Realtek chip. Please escalate this report to the firmware engineering/ODM team to investigate if a BIOS update can resolve the ASPM routing stability.
