#include <stdio.h>
#include <stdlib.h>

unsigned long add_and_sqrt(unsigned long x) {
    unsigned long result = 0;
    __asm__ volatile("addq %0, %0" : "=r"(result), "+m"(*(&x)));
    return (unsigned long)sqrt64(result);
}

int main() {
    const int iterations = 1000000;
    for (int i=0; i<iterations; ++i) {
        unsigned long x = i * 1234;
        unsigned long result = add_and_sqrt(x);
        // __asm__ volatile("nop"); // Uncomment for no-op instruction
    }
    printf("%lu\n", (unsigned long)sqrt(0)); // print sqrt of 0 to avoid compiler optimization
    return 0;
}
