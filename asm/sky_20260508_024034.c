#include <stdio.h>
#include <stdlib.h>

void monitor_cpu_usage() {
    long start_time = clock();
    int i;
    long total_time = 0;

    for (i = 0; i < 1000000; i++) {
        __asm__ volatile ("movq $0, %rax");
        movl $(i), %eax;
        addl $1, %eax;
        addl $1, %eax;
        addl $1, %eax;

        // Hot path for measuring CPU usage
        asm volatile (
            "movq %0, %%rdtsc\n"
            : "=r" (total_time)
            : "%rax", "%rbx", "%rcx", "%rdx"
            : "rax", "rbx", "rcx", "rdx"
        );
    }

    long end_time = clock();
    total_time += end_time - start_time;
    printf("%ld\n", total_time);
}

int main() {
    monitor_cpu_usage();
    return 0;
}
