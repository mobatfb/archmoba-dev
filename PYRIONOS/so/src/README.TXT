PYRION OS v1 - Modular BIOS/UEFI compatibility build
Legacy BIOS: original BIOS113 boot stage (named BIOSBOOT.IMG).
UEFI: original FAT16 EFIBOOT image and original BOOTX64.EFI.
Kernel original preserved in BIOS/UEFI.
Initrd: two byte-identical physical copies retained for boot compatibility.
PYTHON.IMG / PYRION.IMG: gzip + CPIO newc, loaded from CD by /init.
New /init includes matching ISO9660/CDROM kernel drivers.
BOOT remains unchanged in BIOS/UEFI critical sectors.
Real boot in VirtualBox still requires testing.
