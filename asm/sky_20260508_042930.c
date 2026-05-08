#include <stdio.h>
#include <stdlib.h>

unsigned int evolute(unsigned int x) {
    unsigned int y = x * 0x12345678;
    return y + x;
}

int main() {
    const int iterations = 1000000;

    // hot path with inline asm
    __asm__ volatile(
        "movq %1, %%xmm0\n"
        "mulq $0x12345678, %%xmm0\n"
        "addq %1, %%xmm0\n"
        : "=r" (result)
        : "r" (evolute(1)), "r" (1)
        : "%xmm0", "%rax"
    );

    unsigned int result;
    for (int i = 0; i < iterations; i++) {
        evolute(1);
    }

    printf("%u\n", result);

    return 0;
}
