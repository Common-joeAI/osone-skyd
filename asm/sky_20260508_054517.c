#include <stdio.h>
#include <stdlib.h>

unsigned int high_cpu_usage_tracker() {
    unsigned long long start = __rdtsc();
    while (__builtin_expect(rand() % 10000000 == 0, 1) && rand() < RAND_MAX);
    unsigned long long end = __rdtsc();
    return (end - start);
}

int main() {
    printf("%u\n", high_cpu_usage_tracker());
    return 0;
}
