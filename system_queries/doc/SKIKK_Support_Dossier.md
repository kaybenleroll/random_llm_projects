# Technical Support Dossier: SKIKK Thor 16 (Tongfang GM6HG7Y) Power & Thermal Failures

## **Executive Summary**
This system is experiencing unrecoverable soft lockups and severe thermal instability rooted in a firmware/ACPI implementation flaw. The core issue is an undefined ACPI symbol (`\_SB.ACDC.RTAC`) which causes critical power management methods to abort, specifically impacting PCIe ASPM (Active State Power Management) negotiation for the Realtek RTL8125 Ethernet controller.

## **Hardware Information**
*   **Manufacturer:** SKIKK
*   **Chassis (ODM):** Tongfang GM6HG7Y
*   **CPU:** Ryzen 9 (ZEN 4/5)
*   **GPU:** NVIDIA RTX 5070 Ti
*   **Ethernet:** Realtek Semiconductor Co., Ltd. RTL8125 2.5GbE Controller (PCIe ID: 10ec:8125)
*   **OS:** Ubuntu 25.10 / 26.04 LTS (Questing/Resolute)

## **Technical Root Cause: The "RTAC" Bug**
System logs consistently report the following ACPI error during power state transitions and boot:
```text
ACPI BIOS Error (bug): Could not resolve symbol [\_SB.ACDC.RTAC], AE_NOT_FOUND (20250404/psargs-332)
ACPI Error: Aborting method \_SB.PEP._DSM due to previous error (AE_NOT_FOUND) (20250404/psparse-529)
```

Decompilation of the system's SSDT (specifically the `UPEPRPL` table) confirms that the `_DSM` method for the AMD Power Engine Plugin (`PEP`) attempts to access a non-existent `ACDC` device/scope. 

**Offending code block in `UPEPRPL` SSDT:**
```asl
Case (0x04) // Likely S0ix Exit logic
{
    Local0 = \_SB.PCI0.SBRG.EC0.S0E1
    \_SB.PCI0.SBRG.EC0.S0E1 = Zero
    If ((\_SB.ACDC.RTAC == 0x20)) // <--- CRITICAL FAILURE POINT
    {
        \_SB.PCI0.SBRG.EC0.EYER = \_SB.ACDC.YARR
        \_SB.PCI0.SBRG.EC0.EMON = \_SB.ACDC.MONR
    }
    Else
    {
        \_SB.PCI0.SBRG.EC0.EYER = Zero
        \_SB.PCI0.SBRG.EC0.EMON = Zero
    }
    ... // Remaining power state logic is aborted when the line above fails
}
```

The `_PEP` (Power Engine Plugin) `_DSM` (Device Specific Method) is responsible for coordinating deep sleep states and ASPM timings. When it aborts:
1.  **Ethernet Lockup:** The RTL8125 chip enters an unstable power state, flooding the PCIe bus with AER (Advanced Error Reporting) errors.
2.  **Soft Lockup:** The error flood overwhelms the CPU, causing `watchdog: BUG: soft lockup - CPU stuck for 20s+`.

## **Resulting Thermal & Power Instability**
To prevent system crashes, ASPM must be disabled (`pcie_aspm=off`). However, this results in:
*   **Modern Standby Failure:** The PCIe root ports for the dGPU and NVMe drives cannot enter L1.1/L1.2 states.
*   **High Idle Heat:** The laptop maintains a baseline draw of 25W-40W while "sleeping," causing internal temperatures to reach **79°C while the lid is closed.**
*   **Battery Degradation:** Rapid discharge and heat-soak during transport.

## **Requested Action**
Please escalate this to the firmware engineering/ODM team (Tongfang). A BIOS update is required to:
1.  Correctly define the `RTAC` symbol in the ACPI tables.
2.  Ensure valid ASPM timing parameters are passed to the Realtek RTL8125 controller.

## **Empirical Evidence Attached**
*   `journalctl` logs showing RTAC symbol resolution failure.
*   DSDT (Differentiated System Description Table) dump showing missing symbol.
*   Thermal sensor logs showing ALARM (HIGH) states during low-load periods.
