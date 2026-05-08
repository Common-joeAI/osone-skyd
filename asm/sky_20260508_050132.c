#include <stdio.h>
#include <stdlib.h>

long long monitor_cpu_usage() {
    long long start = 0;
    inline __asm__ volatile("rdtsc" : "=A" (start));
    
    long long end = 0;
    inline __asm__ volatile("rdtsc" : "=A" (end));

    return end - start;
}

int main() {
    printf("%lld\n", monitor_cpu_usage());
    return 0;
}
