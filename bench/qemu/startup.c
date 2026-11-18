/* Minimal Cortex-M3 start-up and semihosting for the QEMU benchmark (mps2-an385). */
#include <stdint.h>
#include <string.h>

extern uint32_t _etext, _sdata, _edata, _sbss, _ebss, _stack_top;
int main(void);

static int semi(int op, const void *arg)
{
    register int r0 __asm__("r0") = op;
    register const void *r1 __asm__("r1") = arg;
    __asm__ volatile("bkpt 0xab" : "+r"(r0) : "r"(r1) : "memory");
    return r0;
}

void semi_puts(const char *s)
{
    semi(0x04, s);                              /* SYS_WRITE0 */
}

void semi_exit(int code)
{
    uint32_t args[2] = {0x20026, (uint32_t)code};  /* ADP_Stopped_ApplicationExit */
    semi(0x20, args);                           /* SYS_EXIT_EXTENDED */
    for (;;)
        ;
}

void reset(void)
{
    memcpy(&_sdata, &_etext, (size_t)((char *)&_edata - (char *)&_sdata));
    memset(&_sbss, 0, (size_t)((char *)&_ebss - (char *)&_sbss));
    semi_exit(main());
}

static void fault(void)
{
    semi_puts("FAULT\n");
    semi_exit(3);
}

__attribute__((section(".vectors"), used)) static const void *vectors[16] = {
    &_stack_top, (void *)reset, (void *)fault, (void *)fault, (void *)fault, (void *)fault,
    (void *)fault, 0, 0, 0, 0, (void *)fault, (void *)fault, 0, (void *)fault, (void *)fault,
};
