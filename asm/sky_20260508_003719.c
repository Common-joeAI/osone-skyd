#include <stdio.h>
#include <stdlib.h>

int monitor_resources() {
    long total = 0;
    unsigned long start_time;

    __asm__ volatile (
        "movq %%rdtsc, %0\n"
        : "=r" (start_time)
        :
        : "%rdtsc"
    );

    for (unsigned long i = 0; i < 1000000; ++i) {
        unsigned long cur_time;
        __asm__ volatile (
            "movq %%rdtsc, %0\n"
            : "=r" (cur_time)
            :
            : "%rdtsc"
        );

        if (cur_time > start_time + i * 10) {
            total++;
        }
    }

    printf("ok\n");
    return total;
}

int main() {
    int result = monitor_resources();
    printf("%d\n", result);
    return 0;
}
