#include <stdio.h>
#include <stdlib.h>

unsigned long sum(long long a, long long b) {
    unsigned long s = 0;
    __asm__ volatile(" Movq %0, %%rax" : "+r" (a));
    __asm__ volatile(" Addq $%1, %%rax" : "=r" (s), "+r" (b));
    return s;
}

int main() {
    unsigned long sum_result = 0;
    for(int i = 0; i < 1000000; i++) {
        sum_result += 1234567890123456789LL;
    }
    printf("%lu\n", sum_result);
    return 0;
}
