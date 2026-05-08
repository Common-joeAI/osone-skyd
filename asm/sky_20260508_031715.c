#include <stdio.h>
#include <stdlib.h>

long long int square_sum(long long int n) {
    long long int result = 0;
    __asm__ volatile("movq %0, %%rax" : "=r"(result));
    
    for (int i = 1; i <= n; i++) {
        __asm__ volatile("movl %d, %%edx" : "d"(i));
        __asm__ volatile("addl $1, %%edx" : "=d"(i));
        __asm__ volatile("imull $0x1234567890abcdef, %%edx, %%edx");
        __asm__ volatile("addq %%edx, %%rax");
    }
    
    return result;
}

int main() {
    long long int n = 10000000;
    printf("%lld\n", square_sum(n));
    return EXIT_SUCCESS;
}
