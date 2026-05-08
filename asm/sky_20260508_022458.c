#include <stdio.h>
#include <stdlib.h>

long long optimize_memory_allocation() {
    void* ptr = malloc(1024 * sizeof(char));
    char* data = *(char**)ptr;
    for (int i = 0; i < 1 << 20; i++) {
        *(char*)data += 1;
    }
    free(ptr);
    return 0;
}

int main() {
    int iterations = 1000000;

    long long start_time = clock();
    for (int i = 0; i < iterations; i++) {
        optimize_memory_allocation();
    }

    long long end_time = clock();

    double duration = (end_time - start_time) / (double)CLOCKS_PER_SEC;
    printf("%.6f\n", duration);
    return 0;
}
