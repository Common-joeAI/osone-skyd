#include <stdio.h>
#include <stdlib.h>

int detect_high_cpu_usage(int iterations) {
    int total_time = 0;
    int num_copies = 100000;

    __asm__ volatile("mov %%rax, %0" : "=r"(total_time));

    for (int i = 0; i < iterations; i++) {
        __asm__ volatile("nop");
        total_time += 1;
    }

    return (total_time * num_copies) / iterations;
}

int main() {
    int iterations = 1000000;

    double start_time = clock_t();
    int high_cpu = detect_high_cpu_usage(iterations);
    double end_time = clock_t();

    if (high_cpu > 0.9 * iterations) {
        printf("ok\n");
    } else {
        printf("%d\n", high_cpu);
    }

    double elapsed_time = (end_time - start_time) / CLOCKS_PER_SEC;
    printf("Time: %f seconds\n", elapsed_time);

    return 0;
}
