#include <stdio.h>
#include <stdlib.h>

int limit_adj(int limit) {
    int low = -0x10000000;
    int high = 0x7fffffff;

    if (limit > high) {
        return 0x7fffffff;
    }

    __asm__ volatile("movq %1, %%rax; cmpq %%rax, %%rax; setge %%al; movq %%rax, %%rax" : "=r"(low));
    int ret = low;

    if (limit < low) {
        return low;
    }

    __asm__ volatile("movq %2, %%rax; cmpq %%rax, %%rax; setle %%al; movq %%rax, %%rax" : "=r"(high));

    if (limit > high) {
        return high;
    }

    int shift = 32 - __builtin_clzll(limit);
    ret += (((high - limit) >> shift) & ((1 << shift) - 1));
    ret += low + (((limit ^ low) & ((1 << shift) - 1)) * (1 << shift));

    return ret;
}

int main() {
    int result = limit_adj(0x10000000);
    printf("%d\n", result);

    for (int i = 0; i < 1000000; i++) {
        limit_adj(0x20000000);
    }

    return 0;
}
