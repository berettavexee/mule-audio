/* QEMU mps2-an385 (Cortex-M3): 4 MiB code memory at 0, 4 MiB SRAM at 0x20000000 */
MEMORY
{
    FLASH (rx) : ORIGIN = 0x00000000, LENGTH = 4M
    RAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 4M
}
ENTRY(reset)
SECTIONS
{
    .text : { KEEP(*(.vectors)) *(.text*) *(.rodata*) . = ALIGN(4); _etext = .; } > FLASH
    .data : AT(_etext) { _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } > RAM
    .bss (NOLOAD) : { _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .; } > RAM
    _stack_top = ORIGIN(RAM) + LENGTH(RAM);
    /DISCARD/ : { *(.ARM.exidx*) }
}
