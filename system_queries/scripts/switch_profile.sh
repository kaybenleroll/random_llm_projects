#!/bin/bash
# switch_profile.sh — switch AC fan profile without tccd overwriting the change
# Run as: bash .scratch/switch_profile.sh
set -euo pipefail

SCRATCH="$(cd "$(dirname "$0")" && pwd)"
PROFILE="${1:-thor_gaming}"

echo "=== Switching AC profile to: $PROFILE ==="

# Generate new settings
python3 -c "
import json, sys
with open('/etc/tcc/settings') as f: s = json.load(f)
s['stateMap']['power_ac'] = sys.argv[1]
with open('/etc/tcc/settings', 'w') as f: json.dump(s, f)
print('Written.')
" "$PROFILE" 2>/dev/null || python3 -c "
import json, sys

# If /etc/tcc/settings is unreadable as user, stage in scratch
with open('$SCRATCH/tcc_settings_new.json') as f: s = json.load(f)
s['stateMap']['power_ac'] = sys.argv[1]
with open('$SCRATCH/tcc_settings_staged.json', 'w') as f: json.dump(s, f)
" "$PROFILE"

echo "=== Stopping tccd ==="
sudo systemctl stop tccd
sleep 1

echo "=== Writing settings ==="
sudo cp "$SCRATCH/tcc_settings_staged.json" /etc/tcc/settings 2>/dev/null || \
sudo python3 -c "
import json
with open('/etc/tcc/settings') as f: s = json.load(f)
s['stateMap']['power_ac'] = '$PROFILE'
with open('/etc/tcc/settings', 'w') as f: json.dump(s, f)
"

echo "=== Starting tccd ==="
sudo systemctl start tccd
sleep 2

echo "=== Verifying ==="
python3 -c "import json; s=json.load(open('/etc/tcc/settings')); print('AC profile:', s['stateMap']['power_ac'])"
systemctl is-active tccd

echo ""
echo "=== DSDT OEM revision check ==="
sudo python3 -c "
import struct
with open('/sys/firmware/acpi/tables/DSDT', 'rb') as f:
    hdr = f.read(36)
# OEM Revision at offset 24-28 (Creator Revision at 32-36 is the ACPI compiler version)
oem_rev = struct.unpack('<I', hdr[24:28])[0]
print(f'DSDT OEM Revision: 0x{oem_rev:08X}')
if oem_rev == 0x0107200A:
    print('Firmware: Dec 2025 BIOS — PWUP is empty natively, NVPCF fix not needed')
elif oem_rev == 0x01072009:
    print('Firmware: pre-Dec-2025 BIOS — NVPCF fix via initrd override was needed')
else:
    print(f'Firmware: unknown revision — check .scratch/dsdt_bios_*.dsl for PWUP body')
"
