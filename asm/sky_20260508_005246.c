#include <stdio.h>
#include <stdlib.h>

int main() {
    long long sum = 0;
    int i;
    for (i = 0; i < 1000000; ++i) {
        __asm__ volatile (
            "movl $1, %%eax\n"
            "imull %%eax, %%eax, %%eax\n"
            "addl %2, %%eax\n"
            : "=m" (sum), "=a" (sum)
            : "r" (i), "r" (1LL)
        );
    }
    printf("%lld\n", sum);
    return 0;
}
