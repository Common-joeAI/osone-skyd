#include <stdio.h>
#include <stdlib.h>

int calculate_skylang_result() {
    long long result = 0;
    
    // Hot path: use __asm__ for better performance
    __asm__ volatile("xorps %%xmm0,%%xmm0"
                     "movups $0x1234567890abcdefLL, %%xmm1"
                     "addps %%xmm1,%%xmm0"
                     : "=m" (result)
                     : "r" (0x1234567890abcdefLL)
                     : "%xmm0", "%xmm1");
    
    return result;
}

int main() {
    const int iterations = 1000000;
    for (int i = 0; i < iterations; i++) {
        calculate_skylang_result();
    }
    
    printf("%lld\n", calculate_skylang_result());
    return 0;
}
