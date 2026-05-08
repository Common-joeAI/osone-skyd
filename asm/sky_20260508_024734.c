#include <stdio.h>
#include <stdlib.h>

int monitor_cpu_usage() {
    long long current_time, previous_time;
    __asm__ __volatile__("rdtsc" : "=a" (current_time), "=d" (previous_time));
    
    if (__builtin_expect(current_time != previous_time, 1)) {
        return current_time - previous_time;
    }
    return 0;
}

int main() {
    const int iterations = 1000000;
    long long total = 0;
    for (int i = 0; i < iterations; ++i) {
        total += monitor_cpu_usage();
    }
    
    printf("%.9f\n", (double)total / iterations);
    return 0;
}
