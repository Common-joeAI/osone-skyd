#include <stdio.h>
#include <stdint.h>

int32_t limit_cpu_usage(int64_t workload) {
    int64_t threshold = 1000000;
    if (workload > threshold) {
        return -1; // overload detected
    }
    __asm__ volatile("movq %0, %%rdi" : "=r"(workload));
    return workload;
}

int main() {
    const uint64_t iterations = 1000000;
    for (uint64_t i = 0; i < iterations; i++) {
        int32_t result = limit_cpu_usage(i);
        if (result == -1) break;
    }
    printf("%d\n", result);
    return 0;
}
