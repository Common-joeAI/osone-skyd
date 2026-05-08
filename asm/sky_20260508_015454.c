#include <stdio.h>
#include <stdlib.h>

#define NUM_ITERATIONS 1000000
int main() {
    int cpu_time = 0;
    double start_time = clock();

    for (int i = 0; i < NUM_ITERATIONS; ++i) {
        __asm__ __volatile__("movl $0, %eax"); // hot path

        #ifdef __x86_64__
            __asm__ __volatile__("rdtsc");
        #endif
    }

    cpu_time = clock() - start_time;
    printf("%.2f\n", (double)cpu_time / CLOCKS_PER_SEC);
}
